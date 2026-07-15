from __future__ import annotations

import os
import json
import unicodedata
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd
from sqlalchemy import text

from midway.export.iqs_csv import exportar_dataframe_iqs
from midway.transform.tratamento import (
    LAYOUT_IQS_COLUNAS,
    aplicar_formato_oficial_iqs,
    validar_layout_iqs,
)


ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DIR = BASE_DIR / "processed"
RAW_DIR = BASE_DIR / "raw"
EXPORT_DIR = BASE_DIR / "export" / "correcao_9282"

TARGET_COMPONENTE = "92"
TARGET_CAUSA = "82"
TARGET_TIPO_CHAVE = "RA"
REGIONAIS_IQS_PADRAO = ("CSL", "LES", "NRO", "NRT", "OES")

STOPWORDS = {
    "A",
    "AO",
    "AOS",
    "AS",
    "COM",
    "DA",
    "DAS",
    "DE",
    "DO",
    "DOS",
    "E",
    "EM",
    "ENERGIA",
    "ESPECIFICA",
    "FALTA",
    "IDENTIFICADA",
    "INTERRUPCAO",
    "NA",
    "NAO",
    "NO",
    "NOS",
    "O",
    "OCORRENCIA",
    "OS",
    "PARA",
    "POR",
    "PROVAVEL",
    "RECLAMACAO",
    "RA",
    "REDE",
    "SEM",
}


def processed_path(anomes: str = ANOMES) -> Path:
    return PROCESSED_DIR / f"iqs_adms_processed_{anomes}.duckdb"


def adms_servicos_raw_path(anomes: str = ANOMES) -> Path:
    return RAW_DIR / f"adms_servicos_raw_{anomes}.duckdb"


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _attach_servicos_raw(con: duckdb.DuckDBPyConnection, raw_path: str | Path) -> None:
    databases = con.execute("PRAGMA database_list").fetchall()
    if any(row[1] == "serv_raw" for row in databases):
        return
    con.execute(f"ATTACH {_sql_literal(raw_path)} AS serv_raw (READ_ONLY)")


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE lower(table_name) = lower(?)
            """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _tokens(text: str) -> set[str]:
    clean = _strip_accents(text).upper()
    for old, new in {
        "_": " ",
        "/": " ",
        "-": " ",
        ".": " ",
        ",": " ",
        ";": " ",
        "|": " ",
        "(": " ",
        ")": " ",
    }.items():
        clean = clean.replace(old, new)
    tokens = {
        token
        for token in clean.split()
        if len(token) >= 3 and token not in STOPWORDS and not token.isdigit()
    }
    return _expand_tokens(tokens)


def _expand_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    if tokens & {"ARVORE", "GALHO", "PODA", "VEGETACAO", "VEGETACAO_REDE"}:
        expanded.update({"ARVORE", "GALHO", "PODA", "VEGETACAO"})
    if tokens & {"OSCILACAO", "PISCA", "PISCANDO", "TENSAO", "TENSÃO", "DESEQUILIBRIO"}:
        expanded.update({"OSCILACAO", "TENSAO", "DESEQUILIBRIO"})
    if tokens & {"DANO", "QUEIMA", "QUEIMADO", "EQUIPAMENTO", "DEFEITO", "FALHA"}:
        expanded.update({"DANO", "EQUIPAMENTO", "DEFEITO", "FALHA", "COMPONENTE"})
    if tokens & {"CABO", "FIO", "POSTE", "TRANSFORMADOR", "CONDUTOR", "RAMAL"}:
        expanded.update({"CABO", "FIO", "POSTE", "TRANSFORMADOR", "CONDUTOR", "RAMAL", "EQUIPAMENTO"})
    if tokens & {"FALTA", "DESLIGADO", "DESLIG", "APAGAO", "APAGADO"}:
        expanded.update({"INTERRUPCAO", "FALHA"})
    return expanded


def _reference_query() -> str:
    return """
        SELECT DISTINCT
            NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') AS COD_GRUPO_GCR,
            NULLIF(TRIM(CAST(DESC_GRUPO_GCR AS VARCHAR)), '') AS DESC_GRUPO_GCR,
            LPAD(NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), ''), 2, '0') AS COD_COMP,
            NULLIF(TRIM(CAST(DESC_COMP AS VARCHAR)), '') AS DESC_COMP,
            LPAD(NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), ''), 2, '0') AS COD_CAUSA,
            NULLIF(TRIM(CAST(DESC_CAUSA AS VARCHAR)), '') AS DESC_CAUSA,
            NULLIF(TRIM(CAST(GRUPO_COMPONENTE_REDE AS VARCHAR)), '') AS GRUPO_COMPONENTE_REDE,
            NULLIF(TRIM(CAST(COMPONENTE_REDE AS VARCHAR)), '') AS COMPONENTE_REDE,
            NULLIF(TRIM(CAST(CAUSA_REDE AS VARCHAR)), '') AS CAUSA_REDE
        FROM gold_iqs_referencia_componente_causa
        WHERE NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') IS NOT NULL
          AND NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), '') IS NOT NULL
    """


def _load_base(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    referencia_cte = _reference_query()
    return con.execute(
        f"""
        WITH referencia AS ({referencia_cte}),
        alvo AS (
            SELECT
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                MAX(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '')) AS CONJUNTO,
                MAX(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), '')) AS REGIONAL,
                MAX(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')) AS ALIM_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS NUM_OPER_CHV_INTRP,
                MAX(NULLIF(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR)), '')) AS TIPO_CHV_INTRP,
                MAX(LPAD(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_COMP_ATUAL,
                MAX(LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_CAUSA_ATUAL,
                MAX(NULLIF(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR)), '')) AS VALID_POS_OPERACAO,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_INTERRUPCAO
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
              AND UPPER(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR))) = '{TARGET_TIPO_CHAVE}'
              AND LPAD(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), ''), 2, '0') = '{TARGET_COMPONENTE}'
              AND LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0') = '{TARGET_CAUSA}'
            GROUP BY 1
        ),
        apuracao AS (
            SELECT
                NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') AS NUM_OCORRENCIA_ADMS,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_APURAVEIS,
                SUM(COALESCE(TRY_CAST(CI_LIQUIDO AS DOUBLE), 0)) AS FIC_OCORRENCIA,
                SUM(COALESCE(TRY_CAST(CHI_LIQUIDO AS DOUBLE), 0)) AS DIC_OCORRENCIA
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1
        ),
        reclamacoes AS (
            SELECT
                TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                QTD_RECLAMACOES,
                QTD_UCS_RECLAMANTES,
                TIPOS_RECLAMACAO_PROVAVEIS,
                CAUSAS_PROVAVEIS_RECLAMACAO,
                PREVIAS_CAUSA_RECLAMACAO,
                GRUPOS_CAUSA_IQS,
                GRUPOS_COMPONENTE_IQS,
                QTD_ADERENCIA_ALTA,
                QTD_ADERENCIA_MEDIA
            FROM gold_reclamacao_ocorrencia_resumo
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
        ),
        textos_reclamacao AS (
            SELECT
                TRIM(CAST(g.NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                LEFT(
                    STRING_AGG(
                        DISTINCT TRIM(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')),
                        ' '
                    ),
                    4000
                ) AS TEXTOS_RECLAMACAO
            FROM gold_reclamacao_uc_vinculada g
            JOIN alvo
              ON alvo.NUM_OCORRENCIA_ADMS = TRIM(CAST(g.NUM_OCORRENCIA_ADMS AS VARCHAR))
            WHERE NULLIF(TRIM(CAST(g.NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1
        )
        SELECT
            alvo.*,
            ref.DESC_COMP AS DESC_COMP_ATUAL,
            ref.DESC_CAUSA AS DESC_CAUSA_ATUAL,
            COALESCE(apuracao.UCS_APURAVEIS, alvo.UCS_INTERRUPCAO) AS UCS_APURAVEIS,
            COALESCE(apuracao.FIC_OCORRENCIA, 0) AS FIC_OCORRENCIA,
            COALESCE(apuracao.DIC_OCORRENCIA, 0) AS DIC_OCORRENCIA,
            COALESCE(reclamacoes.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
            COALESCE(reclamacoes.QTD_UCS_RECLAMANTES, 0) AS QTD_UCS_RECLAMANTES,
            reclamacoes.TIPOS_RECLAMACAO_PROVAVEIS,
            reclamacoes.CAUSAS_PROVAVEIS_RECLAMACAO,
            reclamacoes.PREVIAS_CAUSA_RECLAMACAO,
            reclamacoes.GRUPOS_CAUSA_IQS,
            reclamacoes.GRUPOS_COMPONENTE_IQS,
            textos_reclamacao.TEXTOS_RECLAMACAO,
            COALESCE(reclamacoes.QTD_ADERENCIA_ALTA, 0) AS QTD_ADERENCIA_ALTA,
            COALESCE(reclamacoes.QTD_ADERENCIA_MEDIA, 0) AS QTD_ADERENCIA_MEDIA
        FROM alvo
        LEFT JOIN referencia ref
          ON ref.COD_COMP = alvo.COD_COMP_ATUAL
         AND ref.COD_CAUSA = alvo.COD_CAUSA_ATUAL
        LEFT JOIN apuracao
          ON alvo.NUM_OCORRENCIA_ADMS = apuracao.NUM_OCORRENCIA_ADMS
        LEFT JOIN reclamacoes
          ON alvo.NUM_OCORRENCIA_ADMS = reclamacoes.NUM_OCORRENCIA_ADMS
        LEFT JOIN textos_reclamacao
          ON alvo.NUM_OCORRENCIA_ADMS = textos_reclamacao.NUM_OCORRENCIA_ADMS
        """
    ).fetchdf()


def _load_service_pairs(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    referencia_cte = _reference_query()
    return con.execute(
        f"""
        WITH referencia AS ({referencia_cte}),
        alvo AS (
            SELECT DISTINCT TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
              AND UPPER(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR))) = '{TARGET_TIPO_CHAVE}'
              AND LPAD(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), ''), 2, '0') = '{TARGET_COMPONENTE}'
              AND LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0') = '{TARGET_CAUSA}'
        )
        SELECT
            alvo.NUM_SEQ_INTRP,
            LPAD(NULLIF(TRIM(CAST(serv.COD_COMP_SRVE AS VARCHAR)), ''), 2, '0') AS COD_COMP_SERVICO,
            LPAD(NULLIF(TRIM(CAST(serv.COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') AS COD_CAUSA_SERVICO,
            COUNT(*) AS LINHAS_SERVICO,
            COUNT(DISTINCT NULLIF(TRIM(CAST(serv.NUM_SEQ_SERV AS VARCHAR)), '')) AS QTD_SERVICOS,
            STRING_AGG(DISTINCT NULLIF(TRIM(CAST(serv.NUM_SEQ_SERV AS VARCHAR)), ''), ', ' ORDER BY NULLIF(TRIM(CAST(serv.NUM_SEQ_SERV AS VARCHAR)), '')) AS SERVICOS,
            MIN(serv.DTHR_INIC_SRV) AS PRIMEIRO_INICIO_SERVICO,
            MAX(serv.DTHR_FECH_SRV) AS ULTIMO_FECHAMENTO_SERVICO,
            ref.DESC_COMP AS DESC_COMP_SERVICO,
            ref.DESC_CAUSA AS DESC_CAUSA_SERVICO,
            ref.COD_GRUPO_GCR AS COD_GRUPO_GCR_SERVICO,
            ref.DESC_GRUPO_GCR AS DESC_GRUPO_GCR_SERVICO,
            CASE WHEN ref.COD_COMP IS NOT NULL THEN 1 ELSE 0 END AS PAR_SERVICO_VALIDO
        FROM alvo
        JOIN serv_raw.raw_adms_servicos serv
          ON alvo.NUM_SEQ_INTRP = TRIM(CAST(serv.PID_INTRP_SRVE AS VARCHAR))
        LEFT JOIN referencia ref
          ON ref.COD_COMP = LPAD(NULLIF(TRIM(CAST(serv.COD_COMP_SRVE AS VARCHAR)), ''), 2, '0')
         AND ref.COD_CAUSA = LPAD(NULLIF(TRIM(CAST(serv.COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0')
        WHERE NULLIF(TRIM(CAST(serv.PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
        GROUP BY
            alvo.NUM_SEQ_INTRP,
            COD_COMP_SERVICO,
            COD_CAUSA_SERVICO,
            ref.DESC_COMP,
            ref.DESC_CAUSA,
            ref.COD_GRUPO_GCR,
            ref.DESC_GRUPO_GCR,
            PAR_SERVICO_VALIDO
        """
    ).fetchdf()


def _load_reference(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    if not _table_exists(con, "gold_iqs_referencia_componente_causa"):
        return pd.DataFrame()
    return con.execute(_reference_query()).fetchdf()


def _prepare_reference(reference: pd.DataFrame) -> pd.DataFrame:
    if reference.empty:
        return reference
    prepared = reference.copy()
    text_columns = [
        "DESC_GRUPO_GCR",
        "DESC_COMP",
        "DESC_CAUSA",
        "GRUPO_COMPONENTE_REDE",
        "COMPONENTE_REDE",
        "CAUSA_REDE",
    ]
    prepared["TEXTO_REFERENCIA"] = prepared[text_columns].fillna("").agg(" ".join, axis=1)
    prepared["TOKENS_REFERENCIA"] = prepared["TEXTO_REFERENCIA"].map(_tokens)
    prepared = prepared[
        ~(
            prepared["COD_COMP"].astype(str).eq(TARGET_COMPONENTE)
            & prepared["COD_CAUSA"].astype(str).eq(TARGET_CAUSA)
        )
    ].copy()
    prepared = prepared[~prepared["COD_CAUSA"].astype(str).eq(TARGET_CAUSA)].copy()
    return prepared.reset_index(drop=True)


def _score_candidate(evidence_tokens: set[str], candidate_tokens: set[str]) -> tuple[int, str]:
    overlap = sorted(evidence_tokens & candidate_tokens)
    score = len(overlap) * 8

    if evidence_tokens & {"VEGETACAO", "ARVORE", "GALHO", "PODA"} and candidate_tokens & {
        "VEGETACAO",
        "ARVORE",
        "GALHO",
        "PODA",
    }:
        score += 35
    if evidence_tokens & {"OSCILACAO", "TENSAO", "DESEQUILIBRIO"} and candidate_tokens & {
        "OSCILACAO",
        "TENSAO",
        "DESEQUILIBRIO",
    }:
        score += 35
    if evidence_tokens & {"DANO", "EQUIPAMENTO", "DEFEITO", "FALHA", "COMPONENTE"} and candidate_tokens & {
        "DANO",
        "EQUIPAMENTO",
        "DEFEITO",
        "FALHA",
        "COMPONENTE",
    }:
        score += 25
    if evidence_tokens & {"CABO", "FIO", "POSTE", "TRANSFORMADOR", "CONDUTOR", "RAMAL"} and candidate_tokens & {
        "CABO",
        "FIO",
        "POSTE",
        "TRANSFORMADOR",
        "CONDUTOR",
        "RAMAL",
    }:
        score += 20

    return min(score, 100), ", ".join(overlap)


def _suggest_from_complaint(
    row: pd.Series,
    reference_records: list[dict[str, object]],
    oscillation_candidate: dict[str, object] | None,
) -> dict[str, object]:
    evidence_text = _complaint_evidence_text(row)
    upper_evidence = _strip_accents(evidence_text).upper()
    if "OSCILACAO_TENSAO" in upper_evidence or "OSCILACAO TENSAO" in upper_evidence:
        if oscillation_candidate:
            candidate = oscillation_candidate
            return {
                "COD_COMP_SUGERIDO": candidate["COD_COMP"],
                "COD_CAUSA_SUGERIDA": candidate["COD_CAUSA"],
                "DESC_COMP_SUGERIDO": candidate["DESC_COMP"],
                "DESC_CAUSA_SUGERIDA": candidate["DESC_CAUSA"],
                "FONTE_SUGESTAO": "RECLAMACAO",
                "NIVEL_EVIDENCIA": "MEDIA",
                "SCORE_SUGESTAO": 75,
                "TERMOS_COINCIDENTES": "OSCILACAO_TENSAO, 92/38",
                "JUSTIFICATIVA_ALGORITMO": "Reclamação indica oscilação/tensão; componente 92 possui causa 38 válida na referência.",
            }
    evidence_tokens = _tokens(evidence_text)
    if not evidence_tokens or not reference_records:
        return {
            "COD_COMP_SUGERIDO": "",
            "COD_CAUSA_SUGERIDA": "",
            "DESC_COMP_SUGERIDO": "",
            "DESC_CAUSA_SUGERIDA": "",
            "FONTE_SUGESTAO": "SEM_EVIDENCIA",
            "NIVEL_EVIDENCIA": "SEM_EVIDENCIA",
            "SCORE_SUGESTAO": 0,
            "TERMOS_COINCIDENTES": "",
            "JUSTIFICATIVA_ALGORITMO": "Sem serviço válido alternativo e sem texto/classificação de reclamação suficiente.",
        }

    best: dict[str, object] | None = None
    for candidate in reference_records:
        score, terms = _score_candidate(evidence_tokens, candidate["TOKENS_REFERENCIA"])
        if score <= 0:
            continue
        current = {
            "COD_COMP_SUGERIDO": candidate["COD_COMP"],
            "COD_CAUSA_SUGERIDA": candidate["COD_CAUSA"],
            "DESC_COMP_SUGERIDO": candidate["DESC_COMP"],
            "DESC_CAUSA_SUGERIDA": candidate["DESC_CAUSA"],
            "FONTE_SUGESTAO": "RECLAMACAO",
            "NIVEL_EVIDENCIA": "ALTA" if score >= 70 else "MEDIA" if score >= 35 else "BAIXA",
            "SCORE_SUGESTAO": score,
            "TERMOS_COINCIDENTES": terms,
            "JUSTIFICATIVA_ALGORITMO": "Sugestão por coincidência entre reclamação vinculada e descritivos de grupo/componente/causa.",
        }
        if best is None or int(current["SCORE_SUGESTAO"]) > int(best["SCORE_SUGESTAO"]):
            best = current

    if best and int(best["SCORE_SUGESTAO"]) >= 25:
        return best

    return {
        "COD_COMP_SUGERIDO": "",
        "COD_CAUSA_SUGERIDA": "",
        "DESC_COMP_SUGERIDO": "",
        "DESC_CAUSA_SUGERIDA": "",
        "FONTE_SUGESTAO": "RECLAMACAO_GENERICA",
        "NIVEL_EVIDENCIA": "BAIXA",
        "SCORE_SUGESTAO": int(best["SCORE_SUGESTAO"]) if best else 0,
        "TERMOS_COINCIDENTES": best["TERMOS_COINCIDENTES"] if best else "",
        "JUSTIFICATIVA_ALGORITMO": "Reclamação vinculada existe, mas o texto é genérico para trocar 92/82 com segurança.",
    }


def _complaint_evidence_text(row: pd.Series) -> str:
    return " ".join(
        str(row.get(column) or "")
        for column in [
            "TEXTOS_RECLAMACAO",
            "TIPOS_RECLAMACAO_PROVAVEIS",
            "CAUSAS_PROVAVEIS_RECLAMACAO",
        ]
    )


def _suggest_from_service(service_rows: pd.DataFrame) -> dict[str, object] | None:
    if service_rows.empty:
        return None

    valid_rows = service_rows[
        service_rows["PAR_SERVICO_VALIDO"].fillna(0).astype(int).eq(1)
        & ~(
            service_rows["COD_COMP_SERVICO"].astype(str).eq(TARGET_COMPONENTE)
            & service_rows["COD_CAUSA_SERVICO"].astype(str).eq(TARGET_CAUSA)
        )
    ].copy()
    if valid_rows.empty:
        return None

    valid_rows = valid_rows.sort_values(
        ["QTD_SERVICOS", "LINHAS_SERVICO", "COD_COMP_SERVICO", "COD_CAUSA_SERVICO"],
        ascending=[False, False, True, True],
    )
    chosen = valid_rows.iloc[0]
    multiple_pairs = len(valid_rows[["COD_COMP_SERVICO", "COD_CAUSA_SERVICO"]].drop_duplicates()) > 1
    return {
        "COD_COMP_SUGERIDO": chosen["COD_COMP_SERVICO"],
        "COD_CAUSA_SUGERIDA": chosen["COD_CAUSA_SERVICO"],
        "DESC_COMP_SUGERIDO": chosen["DESC_COMP_SERVICO"],
        "DESC_CAUSA_SUGERIDA": chosen["DESC_CAUSA_SERVICO"],
        "FONTE_SUGESTAO": "SERVICO",
        "NIVEL_EVIDENCIA": "ROBUSTA_COM_CONFLITO" if multiple_pairs else "ROBUSTA",
        "SCORE_SUGESTAO": 85 if multiple_pairs else 95,
        "TERMOS_COINCIDENTES": f"{chosen['COD_COMP_SERVICO']}/{chosen['COD_CAUSA_SERVICO']}",
        "JUSTIFICATIVA_ALGORITMO": (
            "Par componente/causa do serviço ADMS é válido na referência IQS; "
            "há múltiplos pares e foi escolhido o mais frequente."
            if multiple_pairs
            else "Par componente/causa do serviço ADMS é válido na referência IQS."
        ),
    }


def _empty_service_summary() -> dict[str, object]:
    return {
        "QTD_SERVICOS": 0,
        "LINHAS_SERVICO": 0,
        "PARES_SERVICO": "",
        "SERVICOS": "",
        "PRIMEIRO_INICIO_SERVICO": pd.NaT,
        "ULTIMO_FECHAMENTO_SERVICO": pd.NaT,
        "QTD_PARES_SERVICO_INVALIDOS": 0,
    }


def _service_summary(service_rows: pd.DataFrame) -> dict[str, object]:
    if service_rows.empty:
        return _empty_service_summary()
    pairs = [
        f"{row.COD_COMP_SERVICO}/{row.COD_CAUSA_SERVICO}"
        for row in service_rows.itertuples(index=False)
        if row.COD_COMP_SERVICO and row.COD_CAUSA_SERVICO
    ]
    services = []
    for value in service_rows["SERVICOS"].dropna().astype(str):
        services.extend(part.strip() for part in value.split(",") if part.strip())
    return {
        "QTD_SERVICOS": int(service_rows["QTD_SERVICOS"].fillna(0).sum()),
        "LINHAS_SERVICO": int(service_rows["LINHAS_SERVICO"].fillna(0).sum()),
        "PARES_SERVICO": ", ".join(sorted(set(pairs))),
        "SERVICOS": ", ".join(sorted(set(services))),
        "PRIMEIRO_INICIO_SERVICO": service_rows["PRIMEIRO_INICIO_SERVICO"].min(),
        "ULTIMO_FECHAMENTO_SERVICO": service_rows["ULTIMO_FECHAMENTO_SERVICO"].max(),
        "QTD_PARES_SERVICO_INVALIDOS": int(
            service_rows["PAR_SERVICO_VALIDO"].fillna(0).astype(int).eq(0).sum()
        ),
    }


def calcular_correcao_9282(
    anomes: str = ANOMES,
    db_path: str | Path | None = None,
    raw_path: str | Path | None = None,
) -> pd.DataFrame:
    db_path = Path(db_path) if db_path else processed_path(anomes)
    raw_path = Path(raw_path) if raw_path else adms_servicos_raw_path(anomes)

    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB processado nao encontrado: {db_path}")
    if not raw_path.exists():
        raise FileNotFoundError(f"DuckDB de servicos ADMS nao encontrado: {raw_path}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        required_tables = [
            "gold_interrupcao_tratada",
            "gold_apuracao_uc",
            "gold_reclamacao_uc_vinculada",
            "gold_reclamacao_ocorrencia_resumo",
            "gold_iqs_referencia_componente_causa",
        ]
        missing = [table for table in required_tables if not _table_exists(con, table)]
        if missing:
            raise RuntimeError("Tabelas necessarias ausentes: " + ", ".join(missing))

        _attach_servicos_raw(con, raw_path)
        base = _load_base(con)
        service_pairs = _load_service_pairs(con)
        reference = _prepare_reference(_load_reference(con))

    if base.empty:
        return base

    service_grouped = {
        str(num_seq): group.copy()
        for num_seq, group in service_pairs.groupby("NUM_SEQ_INTRP", dropna=False)
    }
    reference_records = reference.to_dict("records") if not reference.empty else []
    oscillation_candidates = [
        candidate
        for candidate in reference_records
        if str(candidate.get("COD_COMP")) == TARGET_COMPONENTE
        and str(candidate.get("COD_CAUSA")) == "38"
    ]
    oscillation_candidate = oscillation_candidates[0] if oscillation_candidates else None

    output_rows: list[dict[str, object]] = []
    complaint_suggestion_cache: dict[str, dict[str, object]] = {}
    for _, row in base.iterrows():
        num_seq_intrp = str(row["NUM_SEQ_INTRP"])
        service_rows = service_grouped.get(num_seq_intrp, pd.DataFrame())
        suggestion = _suggest_from_service(service_rows)
        if suggestion is None:
            evidence_text = _complaint_evidence_text(row)
            if evidence_text not in complaint_suggestion_cache:
                complaint_suggestion_cache[evidence_text] = _suggest_from_complaint(
                    row,
                    reference_records,
                    oscillation_candidate,
                )
            suggestion = complaint_suggestion_cache[evidence_text].copy()

        service_info = _service_summary(service_rows)
        action = "RECLASSIFICAR"
        if not suggestion.get("COD_COMP_SUGERIDO") or not suggestion.get("COD_CAUSA_SUGERIDA"):
            action = "MANTER_9282_SEM_EVIDENCIA"
        elif suggestion.get("NIVEL_EVIDENCIA") in {"BAIXA", "ROBUSTA_COM_CONFLITO"}:
            action = "REVISAR_MANUAL"

        output_row = row.to_dict()
        output_row.update(service_info)
        output_row.update(suggestion)
        output_row["ACAO_RECOMENDADA"] = action
        if suggestion.get("FONTE_SUGESTAO") == "RECLAMACAO":
            output_row["ACAO_RECOMENDADA"] = "REVISAR_MANUAL"
        output_rows.append(output_row)

    result = pd.DataFrame(output_rows)
    columns = [
        "ACAO_RECOMENDADA",
        "FONTE_SUGESTAO",
        "NIVEL_EVIDENCIA",
        "SCORE_SUGESTAO",
        "COD_COMP_SUGERIDO",
        "DESC_COMP_SUGERIDO",
        "COD_CAUSA_SUGERIDA",
        "DESC_CAUSA_SUGERIDA",
        "COD_COMP_ATUAL",
        "DESC_COMP_ATUAL",
        "COD_CAUSA_ATUAL",
        "DESC_CAUSA_ATUAL",
        "NUM_OCORRENCIA_ADMS",
        "NUM_SEQ_INTRP",
        "CONJUNTO",
        "REGIONAL",
        "ALIM_INTRP",
        "NUM_OPER_CHV_INTRP",
        "TIPO_CHV_INTRP",
        "VALID_POS_OPERACAO",
        "DATA_HORA_INIC_INTRP",
        "DATA_HORA_FIM_INTRP",
        "UCS_INTERRUPCAO",
        "UCS_APURAVEIS",
        "DIC_OCORRENCIA",
        "FIC_OCORRENCIA",
        "QTD_SERVICOS",
        "LINHAS_SERVICO",
        "PARES_SERVICO",
        "SERVICOS",
        "PRIMEIRO_INICIO_SERVICO",
        "ULTIMO_FECHAMENTO_SERVICO",
        "QTD_PARES_SERVICO_INVALIDOS",
        "QTD_RECLAMACOES",
        "QTD_UCS_RECLAMANTES",
        "TIPOS_RECLAMACAO_PROVAVEIS",
        "CAUSAS_PROVAVEIS_RECLAMACAO",
        "PREVIAS_CAUSA_RECLAMACAO",
        "GRUPOS_CAUSA_IQS",
        "GRUPOS_COMPONENTE_IQS",
        "TEXTOS_RECLAMACAO",
        "QTD_ADERENCIA_ALTA",
        "QTD_ADERENCIA_MEDIA",
        "TERMOS_COINCIDENTES",
        "JUSTIFICATIVA_ALGORITMO",
    ]
    return result.reindex(columns=columns)


def resumo_correcao_9282(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "FONTE_SUGESTAO",
                "NIVEL_EVIDENCIA",
                "ACAO_RECOMENDADA",
                "COD_COMP_SUGERIDO",
                "COD_CAUSA_SUGERIDA",
                "INTERRUPCOES",
                "DIC_TOTAL",
                "RECLAMACOES",
                "SERVICOS",
            ]
        )
    return (
        df.groupby(
            [
                "FONTE_SUGESTAO",
                "NIVEL_EVIDENCIA",
                "ACAO_RECOMENDADA",
                "COD_COMP_SUGERIDO",
                "COD_CAUSA_SUGERIDA",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            INTERRUPCOES=("NUM_SEQ_INTRP", "nunique"),
            DIC_TOTAL=("DIC_OCORRENCIA", "sum"),
            RECLAMACOES=("QTD_RECLAMACOES", "sum"),
            SERVICOS=("QTD_SERVICOS", "sum"),
        )
        .sort_values(["INTERRUPCOES", "DIC_TOTAL"], ascending=[False, False])
    )


def candidatos_automaticos_9282(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    return df[
        df["FONTE_SUGESTAO"].astype(str).eq("SERVICO")
        & df["NIVEL_EVIDENCIA"].astype(str).eq("ROBUSTA")
        & df["ACAO_RECOMENDADA"].astype(str).eq("RECLASSIFICAR")
        & df["COD_COMP_SUGERIDO"].astype(str).str.strip().ne("")
        & df["COD_CAUSA_SUGERIDA"].astype(str).str.strip().ne("")
    ].copy()


def candidatos_manuais_9282(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    return df[
        df["ACAO_RECOMENDADA"].astype(str).eq("REVISAR_MANUAL")
        | df["NIVEL_EVIDENCIA"].astype(str).eq("ROBUSTA_COM_CONFLITO")
    ].copy()


def _normalizar_regional_export(regional: object) -> str:
    value = str(regional or "").strip()
    return value if value else "SEM_REGIONAL"


def _linhas_iqs_correcao_9282(db_path: str | Path, automaticos: pd.DataFrame) -> pd.DataFrame:
    if automaticos.empty:
        return pd.DataFrame(columns=LAYOUT_IQS_COLUNAS)

    chaves = (
        automaticos[["NUM_SEQ_INTRP", "COD_COMP_SUGERIDO", "COD_CAUSA_SUGERIDA"]]
        .astype(str)
        .apply(lambda column: column.str.strip())
        .drop_duplicates(subset=["NUM_SEQ_INTRP"])
    )
    chaves = chaves[chaves["NUM_SEQ_INTRP"].ne("")]
    if chaves.empty:
        return pd.DataFrame(columns=LAYOUT_IQS_COLUNAS)

    with duckdb.connect(str(db_path), read_only=True) as con:
        if not _table_exists(con, "adms_iqs_export"):
            raise RuntimeError(
                "Tabela adms_iqs_export nao encontrada. Execute run.bat exportar ou run.bat tratamento antes."
            )
        con.register("correcao_9282_chaves", chaves[["NUM_SEQ_INTRP"]])
        colunas_export = [row[1] for row in con.execute("PRAGMA table_info('adms_iqs_export')").fetchall()]
        regional_export_expr = (
            "e.REGIONAL_EXPORT AS __REGIONAL_EXPORT"
            if "REGIONAL_EXPORT" in colunas_export
            else "e.SIGLA_REGIONAL AS __REGIONAL_EXPORT"
        )
        base = con.execute(
            f"""
            SELECT e.{", e.".join(LAYOUT_IQS_COLUNAS)},
                   {regional_export_expr}
            FROM adms_iqs_export e
            JOIN correcao_9282_chaves c
              ON TRIM(CAST(e.NUM_SEQ_INTRP AS VARCHAR)) = c.NUM_SEQ_INTRP
            """
        ).fetchdf()

    if base.empty:
        return pd.DataFrame(columns=LAYOUT_IQS_COLUNAS)

    regional_export = base["__REGIONAL_EXPORT"].copy()
    base = base.reindex(columns=LAYOUT_IQS_COLUNAS).copy()
    base["__REGIONAL_EXPORT"] = regional_export
    seq = base["NUM_SEQ_INTRP"].astype(str).str.strip()
    comp_map = chaves.set_index("NUM_SEQ_INTRP")["COD_COMP_SUGERIDO"].to_dict()
    causa_map = chaves.set_index("NUM_SEQ_INTRP")["COD_CAUSA_SUGERIDA"].to_dict()
    mask = seq.isin(comp_map)
    base.loc[mask, "COD_COMP_INTRP"] = seq.loc[mask].map(comp_map)
    base.loc[mask, "COD_CAUSA_INTRP"] = seq.loc[mask].map(causa_map)
    base.loc[mask, "VALID_POS_OPERACAO"] = "S"
    iqs = base.reindex(columns=LAYOUT_IQS_COLUNAS)
    validar_layout_iqs(iqs)
    iqs = aplicar_formato_oficial_iqs(iqs)
    iqs["__REGIONAL_EXPORT"] = base["__REGIONAL_EXPORT"]
    return iqs


def _pg_table(schema: str, table: str) -> str:
    if not schema.replace("_", "").isalnum() or not table.replace("_", "").isalnum():
        raise ValueError("Nome de schema/tabela inválido para PostgreSQL.")
    return f"{schema}.{table}"


def _clean_db_value(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text_value = str(value).strip()
    return text_value or None


def _clean_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _justificativa_auto_9282(row: pd.Series) -> str:
    justificativa = (
        "AUTO 92/82 - Serviço ADMS com par componente/causa válido na referência IQS: "
        f"{row.get('COD_COMP_SUGERIDO')}/{row.get('COD_CAUSA_SUGERIDA')} "
        f"({row.get('DESC_COMP_SUGERIDO')} / {row.get('DESC_CAUSA_SUGERIDA')}). "
        f"Serviços: {row.get('SERVICOS') or ''}. Pares serviço: {row.get('PARES_SERVICO') or ''}."
    )
    return justificativa[:4000]


def _evidencia_manual_9282(row: pd.Series) -> str:
    evidencia = (
        f"Ação: {row.get('ACAO_RECOMENDADA')}; "
        f"fonte: {row.get('FONTE_SUGESTAO')}; "
        f"evidência: {row.get('NIVEL_EVIDENCIA')}; "
        f"score: {row.get('SCORE_SUGESTAO')}; "
        f"serviços: {row.get('SERVICOS') or ''}; "
        f"pares serviço: {row.get('PARES_SERVICO') or ''}; "
        f"termos: {row.get('TERMOS_COINCIDENTES') or ''}; "
        f"justificativa algoritmo: {row.get('JUSTIFICATIVA_ALGORITMO') or ''}."
    )
    return evidencia[:4000]


def _prioridade_manual_9282(row: pd.Series) -> int:
    prioridade = 50
    if str(row.get("NIVEL_EVIDENCIA") or "") == "ROBUSTA_COM_CONFLITO":
        prioridade += 30
    if str(row.get("FONTE_SUGESTAO") or "") == "RECLAMACAO":
        prioridade += 10
    score = _clean_float(row.get("SCORE_SUGESTAO")) or 0
    dic = _clean_float(row.get("DIC_OCORRENCIA")) or 0
    if score >= 70:
        prioridade += 5
    if dic >= 100:
        prioridade += 5
    return min(prioridade, 100)


def registrar_ajustes_automaticos_9282(
    anomes: str = ANOMES,
    db_path: str | Path | None = None,
    raw_path: str | Path | None = None,
    responsavel: str = "EXECUTIVO_9282",
) -> dict[str, object]:
    from midway.web.library.ajuste_manual_iqs import adicionar_ajuste, listar_ajustes

    df = calcular_correcao_9282(anomes, db_path, raw_path)
    automaticos = candidatos_automaticos_9282(df)
    if automaticos.empty:
        return {
            "candidatos": 0,
            "criados": 0,
            "ignorados": 0,
            "manuais": len(candidatos_manuais_9282(df)),
            "ids": [],
        }

    ajustes_existentes = listar_ajustes(anomes)
    chaves_existentes: set[tuple[str, str, str]] = set()
    if not ajustes_existentes.empty:
        for _, ajuste in ajustes_existentes.iterrows():
            chaves_existentes.add(
                (
                    str(ajuste.get("NUM_SEQ_INTRP") or "").strip(),
                    str(ajuste.get("NOVO_COD_COMP_INTRP") or "").strip(),
                    str(ajuste.get("NOVO_COD_CAUSA_INTRP") or "").strip(),
                )
            )

    ids: list[str] = []
    ignorados = 0
    for _, row in automaticos.iterrows():
        chave = (
            str(row.get("NUM_SEQ_INTRP") or "").strip(),
            str(row.get("COD_COMP_SUGERIDO") or "").strip(),
            str(row.get("COD_CAUSA_SUGERIDA") or "").strip(),
        )
        if chave in chaves_existentes:
            ignorados += 1
            continue

        justificativa = (
            "AUTO 92/82 - Serviço ADMS com par componente/causa válido na referência IQS: "
            f"{row.get('COD_COMP_SUGERIDO')}/{row.get('COD_CAUSA_SUGERIDA')} "
            f"({row.get('DESC_COMP_SUGERIDO')} / {row.get('DESC_CAUSA_SUGERIDA')}). "
            f"Serviços: {row.get('SERVICOS') or ''}. Pares serviço: {row.get('PARES_SERVICO') or ''}."
        )
        ajuste_id = adicionar_ajuste(
            anomes,
            {
                "APROVADO": True,
                "ESCOPO": "INTERRUPCAO",
                "NUM_OCORRENCIA_ADMS": str(row.get("NUM_OCORRENCIA_ADMS") or ""),
                "NUM_SEQ_INTRP": str(row.get("NUM_SEQ_INTRP") or ""),
                "SIGLA_REGIONAL": str(row.get("REGIONAL") or ""),
                "NOVO_COD_CAUSA_INTRP": str(row.get("COD_CAUSA_SUGERIDA") or ""),
                "NOVO_COD_COMP_INTRP": str(row.get("COD_COMP_SUGERIDO") or ""),
                "NOVO_VALID_POS_OPERACAO": "S",
                "JUSTIFICATIVA": justificativa[:4000],
                "RESPONSAVEL": responsavel,
            },
        )
        ids.append(ajuste_id)
        chaves_existentes.add(chave)

    return {
        "candidatos": len(automaticos),
        "criados": len(ids),
        "ignorados": ignorados,
        "manuais": len(candidatos_manuais_9282(df)),
        "ids": ids,
    }


def registrar_ajustes_automaticos_9282_postgres(
    anomes: str = ANOMES,
    db_path: str | Path | None = None,
    raw_path: str | Path | None = None,
    responsavel: str = "EXECUTIVO_9282",
    justificativa_autorizacao: str | None = None,
) -> dict[str, object]:
    from midway.db.postgres import create_postgres_engine, get_config

    config = get_config()
    engine = create_postgres_engine(config)
    schema = config.schema

    df = calcular_correcao_9282(anomes, db_path, raw_path)
    automaticos = candidatos_automaticos_9282(df)
    manuais = candidatos_manuais_9282(df)

    if automaticos.empty:
        return {
            "id_autorizacao": None,
            "candidatos": 0,
            "criados": 0,
            "ignorados": 0,
            "manuais": len(manuais),
            "manuais_criados": 0,
            "manuais_ignorados": 0,
            "ids": [],
        }

    ajustes_table = _pg_table(schema, "midway_ajuste_iqs")
    autorizacao_table = _pg_table(schema, "midway_autorizacao_executiva")
    fila_table = _pg_table(schema, "midway_fila_tecnica")
    auditoria_table = _pg_table(schema, "midway_auditoria_evento")

    with engine.begin() as con:
        ajustes_existentes = {
            (
                _clean_db_value(row.num_seq_intrp) or "",
                _clean_db_value(row.novo_cod_comp_intrp) or "",
                _clean_db_value(row.novo_cod_causa_intrp) or "",
            )
            for row in con.execute(
                text(
                    f"""
                    SELECT num_seq_intrp, novo_cod_comp_intrp, novo_cod_causa_intrp
                    FROM {ajustes_table}
                    WHERE anomes = :anomes
                      AND origem_ajuste = 'AUTO_EXECUTIVO_9282'
                    """
                ),
                {"anomes": anomes},
            ).fetchall()
        }

        filas_existentes = {
            (
                _clean_db_value(row.num_seq_intrp) or "",
                _clean_db_value(row.fonte_sugestao) or "",
                _clean_db_value(row.nivel_evidencia) or "",
            )
            for row in con.execute(
                text(
                    f"""
                    SELECT num_seq_intrp, fonte_sugestao, nivel_evidencia
                    FROM {fila_table}
                    WHERE anomes = :anomes
                      AND tipo_fila = 'RA_9282'
                      AND status_fila IN ('ABERTA', 'EM_ANALISE')
                    """
                ),
                {"anomes": anomes},
            ).fetchall()
        }

        ajuste_rows: list[dict[str, object]] = []
        ids: list[str] = []
        for _, row in automaticos.iterrows():
            chave = (
                _clean_db_value(row.get("NUM_SEQ_INTRP")) or "",
                _clean_db_value(row.get("COD_COMP_SUGERIDO")) or "",
                _clean_db_value(row.get("COD_CAUSA_SUGERIDA")) or "",
            )
            if chave in ajustes_existentes:
                continue

            id_ajuste = str(uuid4())
            ids.append(id_ajuste)
            ajuste_rows.append(
                {
                    "id_ajuste": id_ajuste,
                    "anomes": anomes,
                    "aprovado": True,
                    "origem_ajuste": "AUTO_EXECUTIVO_9282",
                    "escopo": "INTERRUPCAO",
                    "num_ocorrencia_adms": _clean_db_value(row.get("NUM_OCORRENCIA_ADMS")),
                    "num_seq_intrp": _clean_db_value(row.get("NUM_SEQ_INTRP")),
                    "sigla_regional": _clean_db_value(row.get("REGIONAL")),
                    "cod_causa_intrp_original": "82",
                    "cod_comp_intrp_original": "92",
                    "novo_cod_causa_intrp": _clean_db_value(row.get("COD_CAUSA_SUGERIDA")),
                    "novo_cod_comp_intrp": _clean_db_value(row.get("COD_COMP_SUGERIDO")),
                    "novo_valid_pos_operacao": "S",
                    "justificativa": _justificativa_auto_9282(row),
                    "criado_por": responsavel,
                    "atualizado_por": responsavel,
                }
            )
            ajustes_existentes.add(chave)

        fila_rows: list[dict[str, object]] = []
        for _, row in manuais.iterrows():
            chave_fila = (
                _clean_db_value(row.get("NUM_SEQ_INTRP")) or "",
                _clean_db_value(row.get("FONTE_SUGESTAO")) or "",
                _clean_db_value(row.get("NIVEL_EVIDENCIA")) or "",
            )
            if chave_fila in filas_existentes:
                continue

            fila_rows.append(
                {
                    "id_fila": str(uuid4()),
                    "anomes": anomes,
                    "tipo_fila": "RA_9282",
                    "prioridade": _prioridade_manual_9282(row),
                    "status_fila": "ABERTA",
                    "num_ocorrencia_adms": _clean_db_value(row.get("NUM_OCORRENCIA_ADMS")),
                    "num_seq_intrp": _clean_db_value(row.get("NUM_SEQ_INTRP")),
                    "cod_causa_atual": "82",
                    "cod_comp_atual": "92",
                    "cod_causa_sugerida": _clean_db_value(row.get("COD_CAUSA_SUGERIDA")),
                    "cod_comp_sugerido": _clean_db_value(row.get("COD_COMP_SUGERIDO")),
                    "fonte_sugestao": _clean_db_value(row.get("FONTE_SUGESTAO")),
                    "nivel_evidencia": _clean_db_value(row.get("NIVEL_EVIDENCIA")),
                    "score_sugestao": _clean_float(row.get("SCORE_SUGESTAO")),
                    "evidencia_resumo": _evidencia_manual_9282(row),
                    "responsavel": responsavel,
                }
            )
            filas_existentes.add(chave_fila)

        id_autorizacao = str(uuid4())
        ignorados = len(automaticos) - len(ajuste_rows)
        manuais_ignorados = len(manuais) - len(fila_rows)
        if not ajuste_rows and not fila_rows:
            return {
                "id_autorizacao": None,
                "candidatos": len(automaticos),
                "criados": 0,
                "ignorados": ignorados,
                "manuais": len(manuais),
                "manuais_criados": 0,
                "manuais_ignorados": manuais_ignorados,
                "ids": [],
            }

        con.execute(
            text(
                f"""
                INSERT INTO {autorizacao_table} (
                    id_autorizacao, anomes, tipo_autorizacao, regra, status_autorizacao,
                    qtd_candidatos, qtd_autorizados, qtd_rejeitados, justificativa,
                    autorizado_por
                )
                VALUES (
                    :id_autorizacao, :anomes, 'RA_9282_AUTO', 'SERVICO+ROBUSTA',
                    'AUTORIZADA', :qtd_candidatos, :qtd_autorizados, :qtd_rejeitados,
                    :justificativa, :autorizado_por
                )
                """
            ),
            {
                "id_autorizacao": id_autorizacao,
                "anomes": anomes,
                "qtd_candidatos": len(automaticos),
                "qtd_autorizados": len(ajuste_rows),
                "qtd_rejeitados": ignorados,
                "justificativa": justificativa_autorizacao or (
                    "Autorização executiva da tratativa automática RA 92/82. "
                    "Critério: serviço ADMS com evidência robusta e par componente/causa válido."
                ),
                "autorizado_por": responsavel,
            },
        )

        if ajuste_rows:
            for row in ajuste_rows:
                row["id_autorizacao"] = id_autorizacao
            con.execute(
                text(
                    f"""
                    INSERT INTO {ajustes_table} (
                        id_ajuste, anomes, aprovado, origem_ajuste, escopo,
                        num_ocorrencia_adms, num_seq_intrp, sigla_regional,
                        cod_causa_intrp_original, cod_comp_intrp_original,
                        novo_cod_causa_intrp, novo_cod_comp_intrp, novo_valid_pos_operacao,
                        justificativa, id_autorizacao, criado_por, atualizado_por
                    )
                    VALUES (
                        :id_ajuste, :anomes, :aprovado, :origem_ajuste, :escopo,
                        :num_ocorrencia_adms, :num_seq_intrp, :sigla_regional,
                        :cod_causa_intrp_original, :cod_comp_intrp_original,
                        :novo_cod_causa_intrp, :novo_cod_comp_intrp, :novo_valid_pos_operacao,
                        :justificativa, :id_autorizacao, :criado_por, :atualizado_por
                    )
                    """
                ),
                ajuste_rows,
            )

        if fila_rows:
            con.execute(
                text(
                    f"""
                    INSERT INTO {fila_table} (
                        id_fila, anomes, tipo_fila, prioridade, status_fila,
                        num_ocorrencia_adms, num_seq_intrp,
                        cod_causa_atual, cod_comp_atual,
                        cod_causa_sugerida, cod_comp_sugerido,
                        fonte_sugestao, nivel_evidencia, score_sugestao,
                        evidencia_resumo, responsavel
                    )
                    VALUES (
                        :id_fila, :anomes, :tipo_fila, :prioridade, :status_fila,
                        :num_ocorrencia_adms, :num_seq_intrp,
                        :cod_causa_atual, :cod_comp_atual,
                        :cod_causa_sugerida, :cod_comp_sugerido,
                        :fonte_sugestao, :nivel_evidencia, :score_sugestao,
                        :evidencia_resumo, :responsavel
                    )
                    """
                ),
                fila_rows,
            )

        con.execute(
            text(
                f"""
                INSERT INTO {auditoria_table} (
                    id_evento, anomes, tipo_evento, entidade, id_entidade, usuario, detalhe
                )
                VALUES (
                    :id_evento, :anomes, 'AUTORIZACAO_9282', 'midway_autorizacao_executiva',
                    :id_entidade, :usuario, CAST(:detalhe AS jsonb)
                )
                """
            ),
            {
                "id_evento": str(uuid4()),
                "anomes": anomes,
                "id_entidade": id_autorizacao,
                "usuario": responsavel,
                "detalhe": json.dumps(
                    {
                        "candidatos_automaticos": len(automaticos),
                        "ajustes_criados": len(ajuste_rows),
                        "ajustes_ignorados": ignorados,
                        "fila_tecnica_criada": len(fila_rows),
                        "fila_tecnica_ignorada": manuais_ignorados,
                    },
                    ensure_ascii=False,
                ),
            },
        )

    return {
        "id_autorizacao": id_autorizacao,
        "candidatos": len(automaticos),
        "criados": len(ajuste_rows),
        "ignorados": ignorados,
        "manuais": len(manuais),
        "manuais_criados": len(fila_rows),
        "manuais_ignorados": manuais_ignorados,
        "ids": ids,
    }


def gerar_exportacao_correcao_9282(
    anomes: str = ANOMES,
    db_path: str | Path | None = None,
    raw_path: str | Path | None = None,
) -> dict[str, object]:
    db_path = db_path or processed_path(anomes)
    df = calcular_correcao_9282(anomes, db_path, raw_path)
    resumo = resumo_correcao_9282(df)
    automaticos = candidatos_automaticos_9282(df)
    iqs_df = _linhas_iqs_correcao_9282(db_path, automaticos)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    detalhe_path = EXPORT_DIR / f"Correcao_RA_9282_{anomes}_{timestamp}_DETALHE.CSV"
    resumo_path = EXPORT_DIR / f"Correcao_RA_9282_{anomes}_{timestamp}_RESUMO.CSV"
    nota_path = EXPORT_DIR / f"Correcao_RA_9282_{anomes}_{timestamp}_NOTA.TXT"
    iqs_paths: list[Path] = []
    iqs_por_regional: dict[str, pd.DataFrame] = {}

    df.to_csv(detalhe_path, sep=";", index=False, encoding="utf-8-sig")
    resumo.to_csv(resumo_path, sep=";", index=False, encoding="utf-8-sig")
    if not iqs_df.empty:
        for regional, regional_df in iqs_df.groupby(iqs_df["__REGIONAL_EXPORT"].map(_normalizar_regional_export)):
            iqs_por_regional[regional] = regional_df.reindex(columns=LAYOUT_IQS_COLUNAS)

    for regional in REGIONAIS_IQS_PADRAO:
        regional_df = iqs_por_regional.get(regional, pd.DataFrame(columns=LAYOUT_IQS_COLUNAS))
        iqs_path = EXPORT_DIR / f"Interrupcoes_IQS_{timestamp}_{regional}.CSV"
        exportar_dataframe_iqs(regional_df, iqs_path)
        iqs_paths.append(iqs_path)

    with nota_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("CORRECAO RA 92/82\n")
        file.write(f"ANOMES: {anomes}\n")
        file.write(f"Interrupcoes RA 92/82: {df['NUM_SEQ_INTRP'].nunique() if not df.empty else 0}\n")
        file.write(f"Com sugestao: {int(df['COD_CAUSA_SUGERIDA'].astype(str).str.len().gt(0).sum()) if not df.empty else 0}\n")
        file.write(f"Automaticos exportados para IQS: {len(automaticos)}\n")
        file.write(f"Linhas IQS exportadas: {len(iqs_df)}\n")
        file.write(f"Detalhe: {detalhe_path}\n")
        file.write(f"Resumo: {resumo_path}\n")
        for iqs_path in iqs_paths:
            file.write(f"Arquivo IQS: {iqs_path}\n")
        file.write("Regra: serviço ADMS válido prevalece; sem serviço válido, usa coincidência textual da reclamação com a referência grupo/componente/causa.\n")

    return {
        "detalhe": detalhe_path,
        "resumo": resumo_path,
        "nota": nota_path,
        "iqs": iqs_paths,
        "linhas": len(df),
        "sugestoes": int(df["COD_CAUSA_SUGERIDA"].astype(str).str.len().gt(0).sum()) if not df.empty else 0,
        "automaticos_iqs": len(automaticos),
        "linhas_iqs": len(iqs_df),
    }


def main() -> None:
    result = gerar_exportacao_correcao_9282(ANOMES)
    print("Exportacao correcao RA 92/82 gerada.")
    print(f"Linhas: {result['linhas']}")
    print(f"Sugestoes: {result['sugestoes']}")
    print(f"Automaticos IQS: {result['automaticos_iqs']}")
    print(f"Linhas IQS: {result['linhas_iqs']}")
    print(f"Detalhe: {result['detalhe']}")
    print(f"Resumo: {result['resumo']}")
    print(f"Nota: {result['nota']}")
    for path in result["iqs"]:
        print(f"Arquivo IQS: {path}")


if __name__ == "__main__":
    main()

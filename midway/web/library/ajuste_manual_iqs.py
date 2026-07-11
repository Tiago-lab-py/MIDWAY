from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import duckdb
import pandas as pd
import streamlit as st

from midway.export.iqs_csv import exportar_dataframe_iqs
from midway.transform.tratamento import (
    LAYOUT_IQS_COLUNAS,
    aplicar_formato_oficial_iqs,
    validar_layout_iqs,
)
from midway.web.library.qualidade_interrupcoes import (
    adms_servicos_raw_path,
    qualidade_ranking,
)
from midway.web.library.shared import (
    DATA_DIR,
    format_number,
    show_metric_cards,
    sql_literal_for_streamlit,
    table_exists,
)


AJUSTE_COLUMNS = [
    "ID_AJUSTE",
    "ANOMES",
    "APROVADO",
    "ESCOPO",
    "NUM_OCORRENCIA_ADMS",
    "NUM_SEQ_INTRP",
    "NUM_UC_UCI",
    "SIGLA_REGIONAL",
    "NOVO_COD_CAUSA_INTRP",
    "NOVO_COD_COMP_INTRP",
    "NOVO_COD_COND_CLIMA_INTRP",
    "NOVO_COD_TIPO_INTRP",
    "NOVO_NUM_MOTIVO_TRAT_DIF_UCI",
    "NOVO_TIPO_PROTOC_JUSTIF_UCI",
    "NOVO_NUM_PROTOC_JUSTIF_RESP_UCI",
    "NOVO_TIPO_PROTOC_JUSTIF_INTRP",
    "NOVO_NUM_PROTOC_JUSTIF_RESP_INTRP",
    "NOVO_VALID_POS_OPERACAO",
    "NOVO_ESTADO_INTRP",
    "NOVA_DATA_HORA_INIC_INTRP",
    "NOVA_DATA_HORA_FIM_INTRP",
    "NOVA_DTHR_INICIO_INTRP_UC",
    "JUSTIFICATIVA",
    "RESPONSAVEL",
    "DTHR_CRIACAO",
    "DTHR_ATUALIZACAO",
]

OVERRIDE_COLUMNS = {
    "NOVO_COD_CAUSA_INTRP": "COD_CAUSA_INTRP",
    "NOVO_COD_COMP_INTRP": "COD_COMP_INTRP",
    "NOVO_COD_COND_CLIMA_INTRP": "COD_COND_CLIMA_INTRP",
    "NOVO_COD_TIPO_INTRP": "COD_TIPO_INTRP",
    "NOVO_NUM_MOTIVO_TRAT_DIF_UCI": "NUM_MOTIVO_TRAT_DIF_UCI",
    "NOVO_TIPO_PROTOC_JUSTIF_UCI": "TIPO_PROTOC_JUSTIF_UCI",
    "NOVO_NUM_PROTOC_JUSTIF_RESP_UCI": "NUM_PROTOC_JUSTIF_RESP_UCI",
    "NOVO_TIPO_PROTOC_JUSTIF_INTRP": "TIPO_PROTOC_JUSTIF_INTRP",
    "NOVO_NUM_PROTOC_JUSTIF_RESP_INTRP": "NUM_PROTOC_JUSTIF_RESP_INTRP",
    "NOVO_VALID_POS_OPERACAO": "VALID_POS_OPERACAO",
    "NOVO_ESTADO_INTRP": "ESTADO_INTRP",
    "NOVA_DATA_HORA_INIC_INTRP": "DATA_HORA_INIC_INTRP",
    "NOVA_DATA_HORA_FIM_INTRP": "DATA_HORA_FIM_INTRP",
    "NOVA_DTHR_INICIO_INTRP_UC": "DTHR_INICIO_INTRP_UC",
}

DATE_OVERRIDE_COLUMNS = {
    "NOVA_DATA_HORA_INIC_INTRP",
    "NOVA_DATA_HORA_FIM_INTRP",
    "NOVA_DTHR_INICIO_INTRP_UC",
}

AJUSTE_COLUMN_TYPES = {
    "ID_AJUSTE": "VARCHAR",
    "ANOMES": "VARCHAR",
    "APROVADO": "BOOLEAN",
    "ESCOPO": "VARCHAR",
    "NUM_OCORRENCIA_ADMS": "VARCHAR",
    "NUM_SEQ_INTRP": "VARCHAR",
    "NUM_UC_UCI": "VARCHAR",
    "SIGLA_REGIONAL": "VARCHAR",
    "NOVO_COD_CAUSA_INTRP": "VARCHAR",
    "NOVO_COD_COMP_INTRP": "VARCHAR",
    "NOVO_COD_COND_CLIMA_INTRP": "VARCHAR",
    "NOVO_COD_TIPO_INTRP": "VARCHAR",
    "NOVO_NUM_MOTIVO_TRAT_DIF_UCI": "VARCHAR",
    "NOVO_TIPO_PROTOC_JUSTIF_UCI": "VARCHAR",
    "NOVO_NUM_PROTOC_JUSTIF_RESP_UCI": "VARCHAR",
    "NOVO_TIPO_PROTOC_JUSTIF_INTRP": "VARCHAR",
    "NOVO_NUM_PROTOC_JUSTIF_RESP_INTRP": "VARCHAR",
    "NOVO_VALID_POS_OPERACAO": "VARCHAR",
    "NOVO_ESTADO_INTRP": "VARCHAR",
    "NOVA_DATA_HORA_INIC_INTRP": "VARCHAR",
    "NOVA_DATA_HORA_FIM_INTRP": "VARCHAR",
    "NOVA_DTHR_INICIO_INTRP_UC": "VARCHAR",
    "JUSTIFICATIVA": "VARCHAR",
    "RESPONSAVEL": "VARCHAR",
    "DTHR_CRIACAO": "TIMESTAMP",
    "DTHR_ATUALIZACAO": "TIMESTAMP",
}

CONTROL_DIR = DATA_DIR / "control"
EXPORT_DIR = DATA_DIR / "export" / "ajuste_manual_iqs"
MARTS_DIR = DATA_DIR / "marts"


def ajustes_db_path(anomes: str) -> Path:
    return CONTROL_DIR / f"iqs_ajustes_manuais_{anomes}.duckdb"


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _clean_value(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "nat"}:
        return ""
    return text


def _bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"1", "S", "SIM", "TRUE", "T", "Y", "YES"}


def _normalize_override_value(source_column: str, value) -> object:
    text = _clean_value(value)
    if not text:
        return ""

    if source_column not in DATE_OVERRIDE_COLUMNS:
        return text

    parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        raise ValueError(
            f"Data/hora invalida em {source_column}: {text}. Use dd/mm/aaaa hh:mm:ss."
        )
    return parsed.to_pydatetime()


def ensure_ajustes_db(anomes: str) -> None:
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    db_path = ajustes_db_path(anomes)
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS ajustes_iqs_manuais (
                ID_AJUSTE VARCHAR PRIMARY KEY,
                ANOMES VARCHAR,
                APROVADO BOOLEAN,
                ESCOPO VARCHAR,
                NUM_OCORRENCIA_ADMS VARCHAR,
                NUM_SEQ_INTRP VARCHAR,
                NUM_UC_UCI VARCHAR,
                SIGLA_REGIONAL VARCHAR,
                NOVO_COD_CAUSA_INTRP VARCHAR,
                NOVO_COD_COMP_INTRP VARCHAR,
                NOVO_COD_COND_CLIMA_INTRP VARCHAR,
                NOVO_COD_TIPO_INTRP VARCHAR,
                NOVO_NUM_MOTIVO_TRAT_DIF_UCI VARCHAR,
                NOVO_TIPO_PROTOC_JUSTIF_UCI VARCHAR,
                NOVO_NUM_PROTOC_JUSTIF_RESP_UCI VARCHAR,
                NOVO_TIPO_PROTOC_JUSTIF_INTRP VARCHAR,
                NOVO_NUM_PROTOC_JUSTIF_RESP_INTRP VARCHAR,
                NOVO_VALID_POS_OPERACAO VARCHAR,
                NOVO_ESTADO_INTRP VARCHAR,
                NOVA_DATA_HORA_INIC_INTRP VARCHAR,
                NOVA_DATA_HORA_FIM_INTRP VARCHAR,
                NOVA_DTHR_INICIO_INTRP_UC VARCHAR,
                JUSTIFICATIVA VARCHAR,
                RESPONSAVEL VARCHAR,
                DTHR_CRIACAO TIMESTAMP,
                DTHR_ATUALIZACAO TIMESTAMP
            )
            """
        )
        existing_columns = {
            row[0]
            for row in con.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'ajustes_iqs_manuais'
                """
            ).fetchall()
        }
        for column in AJUSTE_COLUMNS:
            if column not in existing_columns:
                con.execute(f"ALTER TABLE ajustes_iqs_manuais ADD COLUMN {column} {AJUSTE_COLUMN_TYPES[column]}")


def listar_ajustes(anomes: str) -> pd.DataFrame:
    ensure_ajustes_db(anomes)
    db_path = ajustes_db_path(anomes)
    with duckdb.connect(str(db_path)) as con:
        df = con.execute(
            """
            SELECT *
            FROM ajustes_iqs_manuais
            WHERE ANOMES = ?
            ORDER BY DTHR_ATUALIZACAO DESC, DTHR_CRIACAO DESC
            """,
            [anomes],
        ).fetchdf()

    if df.empty:
        return pd.DataFrame(columns=AJUSTE_COLUMNS)

    return df.reindex(columns=AJUSTE_COLUMNS)


def adicionar_ajuste(anomes: str, payload: dict[str, object]) -> str:
    ensure_ajustes_db(anomes)
    now = datetime.now()
    row = {column: "" for column in AJUSTE_COLUMNS}
    row.update(payload)
    row["ID_AJUSTE"] = row.get("ID_AJUSTE") or uuid4().hex[:12]
    row["ANOMES"] = anomes
    row["APROVADO"] = _bool_value(row.get("APROVADO", True))
    row["DTHR_CRIACAO"] = now
    row["DTHR_ATUALIZACAO"] = now

    values = [row[column] for column in AJUSTE_COLUMNS]
    placeholders = ", ".join(["?"] * len(AJUSTE_COLUMNS))
    columns_sql = ", ".join(AJUSTE_COLUMNS)

    db_path = ajustes_db_path(anomes)
    with duckdb.connect(str(db_path)) as con:
        con.execute(
            f"INSERT INTO ajustes_iqs_manuais ({columns_sql}) VALUES ({placeholders})",
            values,
        )

    return str(row["ID_AJUSTE"])


def salvar_grade_ajustes(anomes: str, df: pd.DataFrame) -> None:
    ensure_ajustes_db(anomes)
    now = datetime.now()
    normalized = df.copy().reindex(columns=AJUSTE_COLUMNS)
    normalized = normalized.astype("object").where(pd.notna(normalized), "")
    normalized["ANOMES"] = anomes
    normalized["ID_AJUSTE"] = normalized["ID_AJUSTE"].map(lambda value: _clean_value(value) or uuid4().hex[:12])
    normalized["APROVADO"] = normalized["APROVADO"].map(_bool_value)
    normalized["DTHR_CRIACAO"] = pd.to_datetime(
        normalized["DTHR_CRIACAO"].map(lambda value: value if _clean_value(value) else now),
        errors="coerce",
    ).fillna(now)
    normalized["DTHR_ATUALIZACAO"] = now

    db_path = ajustes_db_path(anomes)
    with duckdb.connect(str(db_path)) as con:
        con.execute("DELETE FROM ajustes_iqs_manuais WHERE ANOMES = ?", [anomes])
        if not normalized.empty:
            con.register("ajustes_grade_tmp", normalized)
            columns_sql = ", ".join(AJUSTE_COLUMNS)
            con.execute(
                f"INSERT INTO ajustes_iqs_manuais ({columns_sql}) SELECT {columns_sql} FROM ajustes_grade_tmp"
            )
            con.unregister("ajustes_grade_tmp")


def ajustes_aprovados(anomes: str) -> pd.DataFrame:
    ajustes = listar_ajustes(anomes)
    if ajustes.empty:
        return ajustes
    return ajustes[ajustes["APROVADO"].map(_bool_value)].copy()


def _ajuste_condition(row: pd.Series) -> str:
    conditions = []
    occurrence = _clean_value(row.get("NUM_OCORRENCIA_ADMS"))
    interruption = _clean_value(row.get("NUM_SEQ_INTRP"))
    uc = _clean_value(row.get("NUM_UC_UCI"))
    regional = _clean_value(row.get("SIGLA_REGIONAL"))
    scope = _clean_value(row.get("ESCOPO")).upper() or "INTERRUPCAO"

    if occurrence:
        conditions.append(f"TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) = {sql_literal_for_streamlit(occurrence)}")
    if interruption and scope in {"INTERRUPCAO", "UC"}:
        conditions.append(f"TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) = {sql_literal_for_streamlit(interruption)}")
    if uc and scope == "UC":
        conditions.append(f"TRIM(CAST(NUM_UC_UCI AS VARCHAR)) = {sql_literal_for_streamlit(uc)}")
    if regional:
        conditions.append(f"TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = {sql_literal_for_streamlit(regional)}")

    if not conditions:
        return "FALSE"
    return "(" + " AND ".join(conditions) + ")"


def _base_rows_for_adjustments(db_path: str, ajustes: pd.DataFrame) -> pd.DataFrame:
    conditions = [_ajuste_condition(row) for _, row in ajustes.iterrows()]
    where_clause = " OR ".join(condition for condition in conditions if condition != "FALSE")
    if not where_clause:
        return pd.DataFrame(columns=LAYOUT_IQS_COLUNAS)

    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(
            f"""
            SELECT {", ".join(LAYOUT_IQS_COLUNAS)}
            FROM adms_iqs_export
            WHERE {where_clause}
            """
        ).fetchdf()


def _apply_adjustments(df: pd.DataFrame, ajustes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    adjusted = df.copy()
    audit_rows = []

    for _, ajuste in ajustes.iterrows():
        mask = pd.Series(True, index=adjusted.index)
        occurrence = _clean_value(ajuste.get("NUM_OCORRENCIA_ADMS"))
        interruption = _clean_value(ajuste.get("NUM_SEQ_INTRP"))
        uc = _clean_value(ajuste.get("NUM_UC_UCI"))
        regional = _clean_value(ajuste.get("SIGLA_REGIONAL"))
        scope = _clean_value(ajuste.get("ESCOPO")).upper() or "INTERRUPCAO"

        if occurrence:
            mask &= adjusted["NUM_OCORRENCIA_ADMS"].astype(str).str.strip().eq(occurrence)
        if interruption and scope in {"INTERRUPCAO", "UC"}:
            mask &= adjusted["NUM_SEQ_INTRP"].astype(str).str.strip().eq(interruption)
        if uc and scope == "UC":
            mask &= adjusted["NUM_UC_UCI"].astype(str).str.strip().eq(uc)
        if regional:
            mask &= adjusted["SIGLA_REGIONAL"].astype(str).str.strip().eq(regional)

        affected = int(mask.sum())
        changed_fields = []
        for source_column, target_column in OVERRIDE_COLUMNS.items():
            value = _normalize_override_value(source_column, ajuste.get(source_column))
            if value and target_column in adjusted.columns:
                adjusted.loc[mask, target_column] = value
                changed_fields.append(target_column)

        audit_rows.append(
            {
                "ID_AJUSTE": ajuste.get("ID_AJUSTE"),
                "ESCOPO": scope,
                "NUM_OCORRENCIA_ADMS": occurrence,
                "NUM_SEQ_INTRP": interruption,
                "NUM_UC_UCI": uc,
                "SIGLA_REGIONAL": regional,
                "CAMPOS_ALTERADOS": ", ".join(changed_fields),
                "LINHAS_AFETADAS": affected,
                "JUSTIFICATIVA": ajuste.get("JUSTIFICATIVA"),
            }
        )

    return adjusted, pd.DataFrame(audit_rows)


def gerar_exportacao_ajustes(anomes: str, db_path: str) -> dict[str, object]:
    ajustes = ajustes_aprovados(anomes)
    if ajustes.empty:
        raise RuntimeError("Nao ha ajustes aprovados para exportar.")

    if not table_exists(db_path, "adms_iqs_export"):
        raise RuntimeError("Tabela adms_iqs_export nao encontrada. Execute run.bat exportar ou run.bat tratamento.")

    base = _base_rows_for_adjustments(db_path, ajustes)
    if base.empty:
        raise RuntimeError("Nenhuma linha de adms_iqs_export encontrada para os ajustes aprovados.")

    adjusted, audit = _apply_adjustments(base, ajustes)
    adjusted = adjusted.reindex(columns=LAYOUT_IQS_COLUNAS)
    validar_layout_iqs(adjusted)
    adjusted = aplicar_formato_oficial_iqs(adjusted)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    paths = []

    for regional, regional_df in adjusted.groupby(adjusted["SIGLA_REGIONAL"].astype(str).str.strip()):
        regional_name = regional if regional else "SEM_REGIONAL"
        path = EXPORT_DIR / f"AJUSTE_MANUAL_Interrupcoes_IQS_{anomes}_{timestamp}_{regional_name}.CSV"
        exportar_dataframe_iqs(regional_df, path)
        paths.append(path)

    audit_path = MARTS_DIR / f"Ajuste_Manual_IQS_{anomes}_{timestamp}_AUDITORIA.CSV"
    audit.to_csv(audit_path, sep=";", index=False, encoding="utf-8-sig")

    resumo_path = MARTS_DIR / f"Ajuste_Manual_IQS_{anomes}_{timestamp}_RESUMO.TXT"
    with resumo_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("AJUSTE MANUAL IQS\n")
        file.write(f"ANOMES: {anomes}\n")
        file.write(f"Ajustes aprovados: {len(ajustes)}\n")
        file.write(f"Linhas exportadas: {len(adjusted)}\n")
        file.write(f"Arquivos gerados: {len(paths)}\n")
        file.write(f"Auditoria: {audit_path}\n")
        for path in paths:
            file.write(f"Arquivo IQS: {path}\n")

    return {
        "arquivos": paths,
        "auditoria": audit_path,
        "resumo": resumo_path,
        "linhas_exportadas": len(adjusted),
        "ajustes": len(ajustes),
    }


def _first_list_value(value) -> str:
    text = _clean_value(value)
    if not text:
        return ""
    return next((part.strip() for part in text.split(",") if part.strip()), "")


def _candidate_options(candidates: pd.DataFrame) -> dict[str, dict[str, str]]:
    options = {"Preencher manualmente": {}}
    for _, row in candidates.head(200).iterrows():
        causa_servico = _first_list_value(row.get("CAUSAS_SERVICO"))
        componente_servico = _first_list_value(row.get("COMPONENTES_SERVICO"))
        label = (
            f"{_clean_value(row.get('CLASSIFICACAO_QUALIDADE'))} | "
            f"score={_clean_value(row.get('SCORE_QUALIDADE'))} | "
            f"oc={_clean_value(row.get('NUM_OCORRENCIA_ADMS'))} | "
            f"intrp={_clean_value(row.get('NUM_SEQ_INTRP'))}"
        )
        options[label] = {
            "NUM_OCORRENCIA_ADMS": _clean_value(row.get("NUM_OCORRENCIA_ADMS")),
            "NUM_SEQ_INTRP": _clean_value(row.get("NUM_SEQ_INTRP")),
            "SIGLA_REGIONAL": _clean_value(row.get("REGIONAL")),
            "COD_CAUSA_ATUAL": _clean_value(row.get("COD_CAUSA_INTRP")),
            "COD_COMP_ATUAL": _clean_value(row.get("COD_COMP_INTRP")),
            "NOVO_COD_CAUSA_INTRP": causa_servico,
            "NOVO_COD_COMP_INTRP": componente_servico,
            "CLASSIFICACAO_QUALIDADE": _clean_value(row.get("CLASSIFICACAO_QUALIDADE")),
            "SCORE_QUALIDADE": _clean_value(row.get("SCORE_QUALIDADE")),
            "CAUSAS_SERVICO": _clean_value(row.get("CAUSAS_SERVICO")),
            "COMPONENTES_SERVICO": _clean_value(row.get("COMPONENTES_SERVICO")),
            "TIPOS_RECLAMACAO_PROVAVEIS": _clean_value(row.get("TIPOS_RECLAMACAO_PROVAVEIS")),
            "CAUSAS_PROVAVEIS_RECLAMACAO": _clean_value(row.get("CAUSAS_PROVAVEIS_RECLAMACAO")),
            "PREVIAS_CAUSA_RECLAMACAO": _clean_value(row.get("PREVIAS_CAUSA_RECLAMACAO")),
            "JUSTIFICATIVA": _clean_value(row.get("CLASSIFICACAO_QUALIDADE")),
        }
    return options


@st.cache_data(show_spinner=False)
def detalhe_ajuste_ocorrencia(
    db_path: str,
    raw_path: str,
    occurrence: str,
    interruption: str,
    limit: int,
) -> dict[str, pd.DataFrame]:
    occurrence = _clean_value(occurrence)
    interruption = _clean_value(interruption)
    if not occurrence and not interruption:
        return {
            "interrupcao": pd.DataFrame(),
            "reclamacao_resumo": pd.DataFrame(),
            "reclamacoes": pd.DataFrame(),
            "servicos": pd.DataFrame(),
        }

    conditions = []
    if occurrence:
        conditions.append(f"TRIM(CAST(e.NUM_OCORRENCIA_ADMS AS VARCHAR)) = {sql_literal_for_streamlit(occurrence)}")
    if interruption:
        conditions.append(f"TRIM(CAST(e.NUM_SEQ_INTRP AS VARCHAR)) = {sql_literal_for_streamlit(interruption)}")
    where_clause = " AND ".join(conditions)

    with duckdb.connect(db_path, read_only=True) as con:
        interrupcao = con.execute(
            f"""
            SELECT
                e.NUM_OCORRENCIA_ADMS,
                e.NUM_SEQ_INTRP,
                e.SIGLA_REGIONAL,
                e.COD_CONJTO_ELET_ANEEL_INTRP AS CONJUNTO,
                e.ALIM_INTRP,
                e.NUM_OPER_CHV_INTRP,
                MIN(e.DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(e.DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                MIN(e.DTHR_INICIO_INTRP_UC) AS DTHR_INICIO_INTRP_UC,
                e.ESTADO_INTRP,
                e.VALID_POS_OPERACAO,
                e.COD_CAUSA_INTRP,
                c.DESC_CAUSA AS DESC_CAUSA_INTRP,
                e.COD_COMP_INTRP,
                p.DESC_COMP AS DESC_COMP_INTRP,
                e.COD_COND_CLIMA_INTRP,
                e.COD_TIPO_INTRP,
                COUNT(*) AS LINHAS_IQS,
                COUNT(DISTINCT NULLIF(TRIM(CAST(e.NUM_UC_UCI AS VARCHAR)), '')) AS UCS
            FROM adms_iqs_export e
            LEFT JOIN ref_iqs_causa c
              ON LPAD(NULLIF(TRIM(CAST(e.COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0') = c.COD_CAUSA
            LEFT JOIN ref_iqs_componente p
              ON TRIM(CAST(e.COD_COMP_INTRP AS VARCHAR)) = p.COD_COMP
            WHERE {where_clause}
            GROUP BY
                e.NUM_OCORRENCIA_ADMS,
                e.NUM_SEQ_INTRP,
                e.SIGLA_REGIONAL,
                e.COD_CONJTO_ELET_ANEEL_INTRP,
                e.ALIM_INTRP,
                e.NUM_OPER_CHV_INTRP,
                e.ESTADO_INTRP,
                e.VALID_POS_OPERACAO,
                e.COD_CAUSA_INTRP,
                c.DESC_CAUSA,
                e.COD_COMP_INTRP,
                p.DESC_COMP,
                e.COD_COND_CLIMA_INTRP,
                e.COD_TIPO_INTRP
            ORDER BY DATA_HORA_INIC_INTRP, e.NUM_SEQ_INTRP
            LIMIT {int(limit)}
            """
        ).fetchdf()

        intrps = [
            _clean_value(value)
            for value in con.execute(
                f"""
                SELECT DISTINCT e.NUM_SEQ_INTRP
                FROM adms_iqs_export e
                WHERE {where_clause}
                  AND NULLIF(TRIM(CAST(e.NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
                LIMIT 500
                """
            ).fetchdf()["NUM_SEQ_INTRP"].tolist()
        ]

        reclamacao_resumo = pd.DataFrame()
        if occurrence and table_exists(db_path, "gold_reclamacao_ocorrencia_resumo"):
            reclamacao_resumo = con.execute(
                """
                SELECT *
                FROM gold_reclamacao_ocorrencia_resumo
                WHERE TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) = ?
                """,
                [occurrence],
            ).fetchdf()

        reclamacoes = pd.DataFrame()
        if occurrence and table_exists(db_path, "gold_reclamacao_uc_vinculada"):
            reclamacoes = con.execute(
                f"""
                SELECT
                    ID_RECLAMACAO,
                    UC,
                    DTHR_RECLAMACAO,
                    TEXTO_RECLAMACAO,
                    TEXTO_RETORNO,
                    TIPO_RECLAMACAO_PROVAVEL,
                    CAUSA_PROVAVEL_RECLAMACAO,
                    PREVIA_CAUSA_RECLAMACAO,
                    ADERENCIA_RECLAMACAO_CAUSA_IQS,
                    SCORE_VINCULO_RECLAMACAO,
                    DISTANCIA_MINUTOS
                FROM gold_reclamacao_uc_vinculada
                WHERE TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) = ?
                ORDER BY DTHR_RECLAMACAO
                LIMIT {int(limit)}
                """,
                [occurrence],
            ).fetchdf()

    servicos = pd.DataFrame()
    raw_file = Path(raw_path)
    if raw_file.exists() and intrps:
        intrps_sql = ", ".join(sql_literal_for_streamlit(value) for value in intrps)
        with duckdb.connect(db_path, read_only=True) as con:
            con.execute(f"ATTACH {_sql_literal(raw_path)} AS serv_raw (READ_ONLY)")
            servicos = con.execute(
                f"""
                SELECT
                    s.PID_INTRP_SRVE AS NUM_SEQ_INTRP,
                    s.NUM_SEQ_SERV,
                    s.INDIC_EST_SERV_SRV,
                    s.NUM_ORG_EXEC_SRV,
                    s.DTHR_SOLIC_SRV,
                    s.DTHR_DESPACH_SRV,
                    s.DTHR_INIC_SRV,
                    s.DTHR_TERM_SRV,
                    s.DTHR_FECH_SRV,
                    LPAD(NULLIF(TRIM(CAST(s.COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') AS COD_CAUSA_SRVE,
                    c.DESC_CAUSA AS DESC_CAUSA_SRVE,
                    s.COD_COMP_SRVE,
                    p.DESC_COMP AS DESC_COMP_SRVE,
                    s.COD_COND_CLIMA_SRVE,
                    s.QTDE_RECLAM_SRVE
                FROM serv_raw.raw_adms_servicos s
                LEFT JOIN ref_iqs_causa c
                  ON LPAD(NULLIF(TRIM(CAST(s.COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') = c.COD_CAUSA
                LEFT JOIN ref_iqs_componente p
                  ON TRIM(CAST(s.COD_COMP_SRVE AS VARCHAR)) = p.COD_COMP
                WHERE TRIM(CAST(s.PID_INTRP_SRVE AS VARCHAR)) IN ({intrps_sql})
                ORDER BY s.DTHR_SOLIC_SRV, s.NUM_SEQ_SERV
                LIMIT {int(limit)}
                """
            ).fetchdf()

    return {
        "interrupcao": interrupcao,
        "reclamacao_resumo": reclamacao_resumo,
        "reclamacoes": reclamacoes,
        "servicos": servicos,
    }


def _comparison_style(df: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    if "Valor atual IQS" in styles.columns:
        styles["Valor atual IQS"] = ""
    if "Pré-tratado/evidência" in styles.columns:
        styles["Pré-tratado/evidência"] = "color: #052e16; background-color: #bbf7d0"
    if "Sugestão algoritmo" in styles.columns:
        styles["Sugestão algoritmo"] = "color: #052e16; background-color: #bbf7d0"
    if "Ajuste manual" in styles.columns:
        styles["Ajuste manual"] = "color: #111827; background-color: #fde68a"
    return styles


def _manual_adjustment_style(df: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=df.index, columns=df.columns)
    for column in df.columns:
        if column.startswith("NOVO_") or column.startswith("NOVA_"):
            mask = df[column].map(_clean_value).ne("")
            styles.loc[mask, column] = "color: #111827; background-color: #fde68a"
    if "APROVADO" in df.columns:
        approved = df["APROVADO"].map(_bool_value)
        styles.loc[approved, "APROVADO"] = "color: #052e16; background-color: #bbf7d0"
    return styles


def _preview_comparacao(defaults: dict[str, str], detalhes: dict[str, pd.DataFrame]) -> pd.DataFrame:
    interrupcao = detalhes.get("interrupcao", pd.DataFrame())
    reclamacao = detalhes.get("reclamacao_resumo", pd.DataFrame())
    atual = interrupcao.iloc[0].to_dict() if not interrupcao.empty else {}
    recl = reclamacao.iloc[0].to_dict() if not reclamacao.empty else {}

    rows = [
        {
            "Campo": "COD_CAUSA_INTRP",
            "Valor atual IQS": " - ".join(
                part for part in [_clean_value(atual.get("COD_CAUSA_INTRP")), _clean_value(atual.get("DESC_CAUSA_INTRP"))] if part
            ),
            "Pré-tratado/evidência": _clean_value(recl.get("PREVIAS_CAUSA_RECLAMACAO"))
            or _clean_value(defaults.get("CAUSAS_PROVAVEIS_RECLAMACAO")),
            "Sugestão algoritmo": _clean_value(defaults.get("NOVO_COD_CAUSA_INTRP")),
            "Ajuste manual": "",
        },
        {
            "Campo": "COD_COMP_INTRP",
            "Valor atual IQS": " - ".join(
                part for part in [_clean_value(atual.get("COD_COMP_INTRP")), _clean_value(atual.get("DESC_COMP_INTRP"))] if part
            ),
            "Pré-tratado/evidência": _clean_value(recl.get("GRUPOS_COMPONENTE_IQS")),
            "Sugestão algoritmo": _clean_value(defaults.get("NOVO_COD_COMP_INTRP")),
            "Ajuste manual": "",
        },
        {
            "Campo": "DATA_HORA_INIC_INTRP",
            "Valor atual IQS": _clean_value(atual.get("DATA_HORA_INIC_INTRP")),
            "Pré-tratado/evidência": "",
            "Sugestão algoritmo": "",
            "Ajuste manual": "",
        },
        {
            "Campo": "DATA_HORA_FIM_INTRP",
            "Valor atual IQS": _clean_value(atual.get("DATA_HORA_FIM_INTRP")),
            "Pré-tratado/evidência": "",
            "Sugestão algoritmo": "",
            "Ajuste manual": "",
        },
        {
            "Campo": "DTHR_INICIO_INTRP_UC",
            "Valor atual IQS": _clean_value(atual.get("DTHR_INICIO_INTRP_UC")),
            "Pré-tratado/evidência": "",
            "Sugestão algoritmo": "",
            "Ajuste manual": "",
        },
    ]
    return pd.DataFrame(rows)


def _render_evidencias(defaults: dict[str, str], db_path: str, raw_path: Path, sample_limit: int) -> None:
    occurrence = defaults.get("NUM_OCORRENCIA_ADMS", "")
    interruption = defaults.get("NUM_SEQ_INTRP", "")
    if not occurrence and not interruption:
        st.info("Selecione um candidato para carregar evidências da ocorrência.")
        return

    detalhes = detalhe_ajuste_ocorrencia(db_path, str(raw_path), occurrence, interruption, min(sample_limit, 200))
    st.markdown(
        """
        **Legenda visual:** sem cor = valor atual da interrupção/ocorrência; verde = sugestão do algoritmo e informação pré-tratada/evidência; amarelo = ajuste manual registrado.
        """
    )
    preview = _preview_comparacao(defaults, detalhes)
    st.dataframe(preview.style.apply(_comparison_style, axis=None), use_container_width=True, hide_index=True)

    evidence_tabs = st.tabs(["Interrupção/ocorrência", "Serviços ADMS", "Reclamações"])
    with evidence_tabs[0]:
        interrupcao = detalhes["interrupcao"]
        if interrupcao.empty:
            st.info("Sem linhas de interrupção/ocorrência encontradas para o filtro.")
        else:
            st.dataframe(interrupcao, use_container_width=True, hide_index=True)
    with evidence_tabs[1]:
        servicos = detalhes["servicos"]
        if servicos.empty:
            st.info("Sem serviços ADMS vinculados às interrupções selecionadas.")
        else:
            st.dataframe(servicos, use_container_width=True, hide_index=True)
    with evidence_tabs[2]:
        resumo = detalhes["reclamacao_resumo"]
        reclamacoes = detalhes["reclamacoes"]
        if resumo.empty and reclamacoes.empty:
            st.info("Sem reclamações vinculadas à ocorrência.")
        if not resumo.empty:
            st.markdown("#### Resumo")
            st.dataframe(resumo, use_container_width=True, hide_index=True)
        if not reclamacoes.empty:
            st.markdown("#### Detalhe")
            st.dataframe(reclamacoes, use_container_width=True, hide_index=True)


def show_ajuste_manual_iqs(anomes: str, db_path: str, sample_limit: int) -> None:
    st.subheader("Ajuste Manual IQS")
    st.caption(
        "Ambiente técnico para tratar exceções, conflitos e registros que exigem evidências adicionais. "
        "Os ajustes automáticos em massa devem ser autorizados no Executivo; aqui ficam revisão, suporte "
        "e geração controlada do CSV IQS."
    )

    if not table_exists(db_path, "adms_iqs_export"):
        st.info("Tabela `adms_iqs_export` não encontrada. Execute `run.bat exportar` ou `run.bat tratamento` antes.")
        return

    ajustes_path = ajustes_db_path(anomes)
    st.caption(f"Base local de ajustes: `{ajustes_path}`")

    raw_path = adms_servicos_raw_path(anomes)
    
    col_filtro_class, col_filtro_val = st.columns(2)
    with col_filtro_class:
        filtro_classificacao = st.selectbox(
            "Classificação Qualidade",
            [
                "Todos",
                "SUSPEITA_IMPROCEDENTE",
                "SUSPEITA_ATENDIDO_OUTRA_OCORRENCIA",
                "RECLAMACAO_FORTE_SEM_SERVICO",
                "RECLAMACAO_FORTE_REVISAR_CAUSA",
                "MULTIPLOS_SERVICOS_REVISAR",
                "CAUSA_COMPONENTE_COM_EVIDENCIA",
                "SERVICO_SEM_RECLAMACAO",
                "RECLAMACAO_SEM_SERVICO",
                "SEM_EVIDENCIA_COMPLEMENTAR"
            ]
        )
    with col_filtro_val:
        filtro_validacao = st.selectbox(
            "Validação Pós-Operação (Filtro Candidatos)",
            ["Todos", "Somente validados (S)", "Somente pendentes (N)"],
            index=2
        )

    candidates = pd.DataFrame()
    if raw_path.exists():
        try:
            candidates = qualidade_ranking(
                db_path, str(raw_path), filtro_classificacao, True, "", 20, min(sample_limit, 500), filtro_validacao
            )
        except Exception as error:
            st.warning(f"Não foi possível carregar candidatos da qualidade: {error}")

    ajustes = listar_ajustes(anomes)
    aprovados = ajustes[ajustes["APROVADO"].map(_bool_value)] if not ajustes.empty else ajustes
    show_metric_cards(
        [
            ("Ajustes registrados", format_number(len(ajustes), 0), None),
            ("Ajustes aprovados", format_number(len(aprovados), 0), None),
            ("Candidatos qualidade", format_number(len(candidates), 0), None),
        ]
    )

    tabs = st.tabs(["Novo ajuste", "Ajustes registrados", "Exportar IQS"])

    with tabs[0]:
        st.markdown("### Candidatos de qualidade")
        if candidates.empty:
            st.info("Sem candidatos carregados. Você ainda pode preencher o ajuste manualmente.")
        else:
            st.dataframe(
                candidates[
                    [
                        "CLASSIFICACAO_QUALIDADE",
                        "SCORE_QUALIDADE",
                        "NUM_OCORRENCIA_ADMS",
                        "NUM_SEQ_INTRP",
                        "CONJUNTO",
                        "REGIONAL",
                        "COD_CAUSA_INTRP",
                        "COD_COMP_INTRP",
                        "CAUSAS_SERVICO",
                        "COMPONENTES_SERVICO",
                        "QTD_RECLAMACOES",
                        "FIC_OCORRENCIA",
                        "DIC_OCORRENCIA",
                    ]
                ].head(sample_limit),
                use_container_width=True,
                hide_index=True,
            )

        defaults = {}

        st.markdown("### Identificação (Pesquisa e Vínculo)")
        col_scope, col_input, col_btn = st.columns([1, 2, 1])
        with col_scope:
            escopo = st.selectbox("Escopo", ["OCORRENCIA", "INTERRUPCAO", "UC"])
            
        ocorrencia = defaults.get("NUM_OCORRENCIA_ADMS", "")
        interrupcao = defaults.get("NUM_SEQ_INTRP", "")
        uc = ""
        
        with col_input:
            if escopo == "OCORRENCIA":
                ocorrencia = st.text_input("NUM_OCORRENCIA_ADMS", value=ocorrencia)
            elif escopo == "INTERRUPCAO":
                interrupcao = st.text_input("NUM_SEQ_INTRP", value=interrupcao)
            elif escopo == "UC":
                uc = st.text_input("NUM_UC_UCI", value="")
                
        with col_btn:
            st.write("")
            st.write("")
            buscar = st.button("Buscar evidências")

        evidence_defaults = defaults.copy()
        if ocorrencia or interrupcao or uc:
            evidence_defaults["NUM_OCORRENCIA_ADMS"] = ocorrencia
            evidence_defaults["NUM_SEQ_INTRP"] = interrupcao
            evidence_defaults["NUM_UC_UCI"] = uc

        if buscar or evidence_defaults.get("NUM_OCORRENCIA_ADMS") or evidence_defaults.get("NUM_SEQ_INTRP"):
            st.markdown("### Evidências para decisão")
            _render_evidencias(evidence_defaults, db_path, raw_path, sample_limit)

        with st.form("form_novo_ajuste_iqs"):
            col_resp, col_aprov = st.columns([2, 1])
            with col_resp:
                responsavel = st.text_input("Responsável", value="")
            with col_aprov:
                aprovado = st.checkbox("Aprovado para exportar", value=True)

            st.markdown("#### Campos IQS a alterar")
            col_causa, col_comp, col_clima, col_tipo = st.columns(4)
            with col_causa:
                novo_causa = st.text_input("COD_CAUSA_INTRP", value=defaults.get("NOVO_COD_CAUSA_INTRP", ""))
            with col_comp:
                novo_comp = st.text_input("COD_COMP_INTRP", value=defaults.get("NOVO_COD_COMP_INTRP", ""))
            with col_clima:
                novo_clima = st.text_input("COD_COND_CLIMA_INTRP", value="")
            with col_tipo:
                novo_tipo = st.text_input("COD_TIPO_INTRP", value="")

            col_motivo, col_tipo_uci, col_prot_uci = st.columns(3)
            with col_motivo:
                novo_motivo = st.text_input("NUM_MOTIVO_TRAT_DIF_UCI", value="")
            with col_tipo_uci:
                novo_tipo_prot_uci = st.text_input("TIPO_PROTOC_JUSTIF_UCI", value="")
            with col_prot_uci:
                novo_prot_uci = st.text_input("NUM_PROTOC_JUSTIF_RESP_UCI", value="")

            col_tipo_intrp, col_prot_intrp, col_valid, col_estado = st.columns(4)
            with col_tipo_intrp:
                novo_tipo_prot_intrp = st.text_input("TIPO_PROTOC_JUSTIF_INTRP", value="")
            with col_prot_intrp:
                novo_prot_intrp = st.text_input("NUM_PROTOC_JUSTIF_RESP_INTRP", value="")
            with col_valid:
                novo_valid = st.text_input("VALID_POS_OPERACAO", value="S")
            with col_estado:
                novo_estado = st.text_input("ESTADO_INTRP", value="")

            st.markdown("#### Data/hora da ocorrência")
            col_ini, col_fim, col_ini_uc = st.columns(3)
            with col_ini:
                nova_data_ini = st.text_input(
                    "DATA_HORA_INIC_INTRP",
                    value="",
                    help="Opcional. Use dd/mm/aaaa hh:mm:ss.",
                )
            with col_fim:
                nova_data_fim = st.text_input(
                    "DATA_HORA_FIM_INTRP",
                    value="",
                    help="Opcional. Use dd/mm/aaaa hh:mm:ss.",
                )
            with col_ini_uc:
                nova_data_ini_uc = st.text_input(
                    "DTHR_INICIO_INTRP_UC",
                    value="",
                    help="Opcional. Use dd/mm/aaaa hh:mm:ss.",
                )

            justificativa = st.text_area("Justificativa/evidência", value=defaults.get("JUSTIFICATIVA", ""), height=100)
            submitted = st.form_submit_button("Adicionar ajuste")

        if submitted:
            try:
                ajuste_id = adicionar_ajuste(
                    anomes,
                    {
                        "APROVADO": aprovado,
                        "ESCOPO": escopo,
                        "NUM_OCORRENCIA_ADMS": ocorrencia,
                        "NUM_SEQ_INTRP": interrupcao,
                        "NUM_UC_UCI": uc,
                        "SIGLA_REGIONAL": defaults.get("SIGLA_REGIONAL", ""),
                        "NOVO_COD_CAUSA_INTRP": novo_causa,
                        "NOVO_COD_COMP_INTRP": novo_comp,
                        "NOVO_COD_COND_CLIMA_INTRP": novo_clima,
                        "NOVO_COD_TIPO_INTRP": novo_tipo,
                        "NOVO_NUM_MOTIVO_TRAT_DIF_UCI": novo_motivo,
                        "NOVO_TIPO_PROTOC_JUSTIF_UCI": novo_tipo_prot_uci,
                        "NOVO_NUM_PROTOC_JUSTIF_RESP_UCI": novo_prot_uci,
                        "NOVO_TIPO_PROTOC_JUSTIF_INTRP": novo_tipo_prot_intrp,
                        "NOVO_NUM_PROTOC_JUSTIF_RESP_INTRP": novo_prot_intrp,
                        "NOVO_VALID_POS_OPERACAO": novo_valid,
                        "NOVO_ESTADO_INTRP": novo_estado,
                        "NOVA_DATA_HORA_INIC_INTRP": nova_data_ini,
                        "NOVA_DATA_HORA_FIM_INTRP": nova_data_fim,
                        "NOVA_DTHR_INICIO_INTRP_UC": nova_data_ini_uc,
                        "JUSTIFICATIVA": justificativa,
                        "RESPONSAVEL": responsavel,
                    },
                )
                st.success(f"Ajuste registrado: `{ajuste_id}`")
                st.cache_data.clear()
            except Exception as error:
                st.error(f"Falha ao registrar ajuste: {error}")

    with tabs[1]:
        st.markdown("### Grade de ajustes")
        ajustes = listar_ajustes(anomes)
        if not ajustes.empty:
            visual_columns = [
                "APROVADO",
                "ESCOPO",
                "NUM_OCORRENCIA_ADMS",
                "NUM_SEQ_INTRP",
                "NUM_UC_UCI",
                "SIGLA_REGIONAL",
                "NOVO_COD_CAUSA_INTRP",
                "NOVO_COD_COMP_INTRP",
                "NOVA_DATA_HORA_INIC_INTRP",
                "NOVA_DATA_HORA_FIM_INTRP",
                "NOVA_DTHR_INICIO_INTRP_UC",
                "JUSTIFICATIVA",
            ]
            visual = ajustes[[column for column in visual_columns if column in ajustes.columns]].head(sample_limit)
            st.markdown("#### Prévia visual")
            st.caption("Amarelo indica campo alterado manualmente; verde indica ajuste aprovado.")
            st.dataframe(visual.style.apply(_manual_adjustment_style, axis=None), use_container_width=True, hide_index=True)
        edited = st.data_editor(
            ajustes,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            disabled=["ID_AJUSTE", "ANOMES", "DTHR_CRIACAO", "DTHR_ATUALIZACAO"],
            column_config={
                "APROVADO": st.column_config.CheckboxColumn("Aprovado"),
                "JUSTIFICATIVA": st.column_config.TextColumn("Justificativa", width="large"),
            },
        )
        if st.button("Salvar alterações da grade"):
            try:
                salvar_grade_ajustes(anomes, edited)
                st.success("Grade de ajustes salva.")
                st.cache_data.clear()
            except Exception as error:
                st.error(f"Falha ao salvar grade: {error}")

    with tabs[2]:
        st.markdown("### Gerar arquivo IQS corrigido")
        st.warning(
            "A exportação usa somente ajustes aprovados e gera linhas encontradas em `adms_iqs_export`. "
            "Conferir auditoria antes da carga no IQS."
        )
        if st.button("Gerar CSV IQS corrigido", type="primary"):
            try:
                resultado = gerar_exportacao_ajustes(anomes, db_path)
                st.success(
                    f"Exportação gerada: {resultado['linhas_exportadas']} linhas em "
                    f"{len(resultado['arquivos'])} arquivo(s)."
                )
                for path in resultado["arquivos"]:
                    st.write(f"Arquivo IQS: `{path}`")
                    st.download_button(
                        f"Baixar {path.name}",
                        data=path.read_bytes(),
                        file_name=path.name,
                        mime="text/csv",
                    )
                st.write(f"Auditoria: `{resultado['auditoria']}`")
                st.write(f"Resumo: `{resultado['resumo']}`")
            except Exception as error:
                st.error(f"Falha ao gerar exportação: {error}")

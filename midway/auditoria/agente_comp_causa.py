from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

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
EXPORT_DIR = BASE_DIR / "export" / "agente_comp_causa"


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


def _required_tables(con: duckdb.DuckDBPyConnection) -> None:
    required = [
        "gold_interrupcao_tratada",
        "gold_apuracao_uc",
        "gold_iqs_referencia_componente_causa",
    ]
    missing = [table for table in required if not _table_exists(con, table)]
    if missing:
        raise RuntimeError("Tabelas obrigatórias ausentes no processado: " + ", ".join(missing))


def _base_query() -> str:
    return """
        WITH referencia AS (
            SELECT DISTINCT
                NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') AS COD_COMP,
                NULLIF(TRIM(CAST(DESC_COMP AS VARCHAR)), '') AS DESC_COMP,
                LPAD(NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), ''), 2, '0') AS COD_CAUSA,
                NULLIF(TRIM(CAST(DESC_CAUSA AS VARCHAR)), '') AS DESC_CAUSA,
                NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') AS COD_GRUPO_GCR,
                NULLIF(TRIM(CAST(DESC_GRUPO_GCR AS VARCHAR)), '') AS DESC_GRUPO_GCR
            FROM gold_iqs_referencia_componente_causa
            WHERE NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), '') IS NOT NULL
        ),
        interrupcoes AS (
            SELECT
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                MAX(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '')) AS CONJUNTO,
                MAX(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), '')) AS REGIONAL,
                MAX(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')) AS ALIM_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS NUM_OPER_CHV_INTRP,
                MAX(NULLIF(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR)), '')) AS TIPO_CHV_INTRP,
                MAX(LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_CAUSA_ATUAL,
                MAX(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), '')) AS COD_COMP_ATUAL,
                MAX(NULLIF(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR)), '')) AS VALID_POS_OPERACAO,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_INTERRUPCAO
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
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
        servico_pares AS (
            SELECT
                NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') AS NUM_SEQ_INTRP,
                NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), '') AS COD_COMP_SERVICO,
                LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') AS COD_CAUSA_SERVICO,
                COUNT(*) AS LINHAS_SERVICO_PAR,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), '')) AS QTD_SERVICOS_PAR,
                STRING_AGG(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), ''), ', ') AS SERVICOS_PAR
            FROM serv_raw.raw_adms_servicos
            WHERE NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1, 2, 3
        ),
        servico_enriquecido AS (
            SELECT
                sp.*,
                CASE WHEN ref.COD_COMP IS NOT NULL THEN 1 ELSE 0 END AS PAR_SERVICO_VALIDO,
                ref.DESC_COMP AS DESC_COMP_SERVICO,
                ref.DESC_CAUSA AS DESC_CAUSA_SERVICO
            FROM servico_pares sp
            LEFT JOIN referencia ref
              ON ref.COD_COMP = sp.COD_COMP_SERVICO
             AND ref.COD_CAUSA = sp.COD_CAUSA_SERVICO
        ),
        servico_totais AS (
            SELECT
                NUM_SEQ_INTRP,
                SUM(LINHAS_SERVICO_PAR) AS LINHAS_SERVICO_TOTAL,
                SUM(QTD_SERVICOS_PAR) AS QTD_SERVICOS_TOTAL,
                COUNT(*) AS QTD_PARES_SERVICO,
                SUM(PAR_SERVICO_VALIDO) AS QTD_PARES_SERVICO_VALIDOS,
                STRING_AGG(DISTINCT COD_COMP_SERVICO || '/' || COD_CAUSA_SERVICO, ', ') AS PARES_SERVICO
            FROM servico_enriquecido
            GROUP BY 1
        ),
        servico_rank AS (
            SELECT
                se.*,
                st.LINHAS_SERVICO_TOTAL,
                st.QTD_SERVICOS_TOTAL,
                st.QTD_PARES_SERVICO,
                st.QTD_PARES_SERVICO_VALIDOS,
                st.PARES_SERVICO,
                ROW_NUMBER() OVER (
                    PARTITION BY se.NUM_SEQ_INTRP
                    ORDER BY
                        se.PAR_SERVICO_VALIDO DESC,
                        se.LINHAS_SERVICO_PAR DESC,
                        se.QTD_SERVICOS_PAR DESC,
                        se.COD_COMP_SERVICO,
                        se.COD_CAUSA_SERVICO
                ) AS ORDEM_SERVICO
            FROM servico_enriquecido se
            JOIN servico_totais st
              ON se.NUM_SEQ_INTRP = st.NUM_SEQ_INTRP
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
                CAST(QTD_ADERENCIA_ALTA AS BIGINT) AS QTD_ADERENCIA_ALTA,
                CAST(QTD_ADERENCIA_MEDIA AS BIGINT) AS QTD_ADERENCIA_MEDIA
            FROM gold_reclamacao_ocorrencia_resumo
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
        ),
        base AS (
            SELECT
                i.NUM_SEQ_INTRP,
                i.NUM_OCORRENCIA_ADMS,
                i.CONJUNTO,
                i.REGIONAL,
                i.ALIM_INTRP,
                i.NUM_OPER_CHV_INTRP,
                i.TIPO_CHV_INTRP,
                i.COD_COMP_ATUAL,
                i.COD_CAUSA_ATUAL,
                ref_atual.DESC_COMP AS DESC_COMP_ATUAL,
                ref_atual.DESC_CAUSA AS DESC_CAUSA_ATUAL,
                CASE WHEN ref_atual.COD_COMP IS NOT NULL THEN 1 ELSE 0 END AS PAR_ATUAL_VALIDO,
                sr.COD_COMP_SERVICO AS COD_COMP_SUGERIDO,
                sr.COD_CAUSA_SERVICO AS COD_CAUSA_SUGERIDA,
                sr.DESC_COMP_SERVICO AS DESC_COMP_SUGERIDO,
                sr.DESC_CAUSA_SERVICO AS DESC_CAUSA_SUGERIDA,
                COALESCE(sr.PAR_SERVICO_VALIDO, 0) AS PAR_SERVICO_SUGERIDO_VALIDO,
                COALESCE(sr.LINHAS_SERVICO_PAR, 0) AS LINHAS_SERVICO_SUGERIDO,
                COALESCE(sr.QTD_SERVICOS_PAR, 0) AS QTD_SERVICOS_SUGERIDO,
                COALESCE(sr.LINHAS_SERVICO_TOTAL, 0) AS LINHAS_SERVICO_TOTAL,
                COALESCE(sr.QTD_SERVICOS_TOTAL, 0) AS QTD_SERVICOS_TOTAL,
                COALESCE(sr.QTD_PARES_SERVICO, 0) AS QTD_PARES_SERVICO,
                COALESCE(sr.QTD_PARES_SERVICO_VALIDOS, 0) AS QTD_PARES_SERVICO_VALIDOS,
                sr.PARES_SERVICO,
                CASE
                    WHEN COALESCE(sr.LINHAS_SERVICO_TOTAL, 0) > 0
                    THEN ROUND(100.0 * sr.LINHAS_SERVICO_PAR / sr.LINHAS_SERVICO_TOTAL, 2)
                    ELSE 0
                END AS PCT_DOMINANCIA_SERVICO,
                COALESCE(r.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
                COALESCE(r.QTD_UCS_RECLAMANTES, 0) AS QTD_UCS_RECLAMANTES,
                COALESCE(r.QTD_ADERENCIA_ALTA, 0) AS QTD_ADERENCIA_ALTA,
                COALESCE(r.QTD_ADERENCIA_MEDIA, 0) AS QTD_ADERENCIA_MEDIA,
                r.TIPOS_RECLAMACAO_PROVAVEIS,
                r.CAUSAS_PROVAVEIS_RECLAMACAO,
                r.PREVIAS_CAUSA_RECLAMACAO,
                r.GRUPOS_CAUSA_IQS,
                r.GRUPOS_COMPONENTE_IQS,
                COALESCE(a.UCS_APURAVEIS, i.UCS_INTERRUPCAO) AS UCS_APURAVEIS,
                COALESCE(a.FIC_OCORRENCIA, 0) AS FIC_OCORRENCIA,
                COALESCE(a.DIC_OCORRENCIA, 0) AS DIC_OCORRENCIA,
                i.VALID_POS_OPERACAO,
                i.DATA_HORA_INIC_INTRP,
                i.DATA_HORA_FIM_INTRP
            FROM interrupcoes i
            LEFT JOIN referencia ref_atual
              ON ref_atual.COD_COMP = i.COD_COMP_ATUAL
             AND ref_atual.COD_CAUSA = i.COD_CAUSA_ATUAL
            LEFT JOIN servico_rank sr
              ON sr.NUM_SEQ_INTRP = i.NUM_SEQ_INTRP
             AND sr.ORDEM_SERVICO = 1
            LEFT JOIN apuracao a
              ON a.NUM_OCORRENCIA_ADMS = i.NUM_OCORRENCIA_ADMS
            LEFT JOIN reclamacoes r
              ON r.NUM_OCORRENCIA_ADMS = i.NUM_OCORRENCIA_ADMS
        )
        SELECT
            *,
            CASE
                WHEN PAR_SERVICO_SUGERIDO_VALIDO = 1
                 AND PCT_DOMINANCIA_SERVICO >= 60
                 AND (
                    COALESCE(COD_COMP_SUGERIDO, '') <> COALESCE(COD_COMP_ATUAL, '')
                    OR COALESCE(COD_CAUSA_SUGERIDA, '') <> COALESCE(COD_CAUSA_ATUAL, '')
                 )
                    THEN 'AJUSTE_PROVAVEL_SERVICO'
                WHEN PAR_ATUAL_VALIDO = 0
                    THEN 'PAR_ATUAL_FORA_REFERENCIA'
                WHEN QTD_PARES_SERVICO > 0 AND QTD_PARES_SERVICO_VALIDOS = 0
                    THEN 'SERVICO_SEM_PAR_VALIDO'
                WHEN PAR_SERVICO_SUGERIDO_VALIDO = 1
                 AND (
                    COALESCE(COD_COMP_SUGERIDO, '') <> COALESCE(COD_COMP_ATUAL, '')
                    OR COALESCE(COD_CAUSA_SUGERIDA, '') <> COALESCE(COD_CAUSA_ATUAL, '')
                 )
                    THEN 'REVISAR_SERVICO_DIVERGENTE'
                WHEN QTD_RECLAMACOES >= 10 AND (QTD_ADERENCIA_ALTA > 0 OR QTD_ADERENCIA_MEDIA > 0)
                    THEN 'REVISAR_RECLAMACAO_FORTE'
                ELSE 'SEM_AJUSTE_PRIORITARIO'
            END AS DECISAO_AGENTE,
            LEAST(
                100,
                CASE WHEN PAR_SERVICO_SUGERIDO_VALIDO = 1
                       AND (
                            COALESCE(COD_COMP_SUGERIDO, '') <> COALESCE(COD_COMP_ATUAL, '')
                            OR COALESCE(COD_CAUSA_SUGERIDA, '') <> COALESCE(COD_CAUSA_ATUAL, '')
                       )
                    THEN 45 ELSE 0 END
                + CASE WHEN PCT_DOMINANCIA_SERVICO >= 80 THEN 15 WHEN PCT_DOMINANCIA_SERVICO >= 60 THEN 10 ELSE 0 END
                + CASE WHEN PAR_ATUAL_VALIDO = 0 THEN 20 ELSE 0 END
                + CASE WHEN QTD_RECLAMACOES >= 10 THEN 10 WHEN QTD_RECLAMACOES >= 3 THEN 5 ELSE 0 END
                + CASE WHEN QTD_ADERENCIA_ALTA > 0 THEN 10 WHEN QTD_ADERENCIA_MEDIA > 0 THEN 5 ELSE 0 END
                + CASE WHEN DIC_OCORRENCIA >= 100 THEN 10 WHEN DIC_OCORRENCIA >= 20 THEN 5 ELSE 0 END
            ) AS SCORE_AGENTE
        FROM base
    """


def analisar_componentes_causas(
    anomes: str = ANOMES,
    db_path: str | Path | None = None,
    raw_path: str | Path | None = None,
    min_score: int = 50,
    incluir_sem_ajuste: bool = False,
    incluir_9282: bool = False,
) -> pd.DataFrame:
    db_path = Path(db_path) if db_path else processed_path(anomes)
    raw_path = Path(raw_path) if raw_path else adms_servicos_raw_path(anomes)

    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB processado nao encontrado: {db_path}")
    if not raw_path.exists():
        raise FileNotFoundError(f"DuckDB de servicos ADMS nao encontrado: {raw_path}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        _required_tables(con)
        _attach_servicos_raw(con, raw_path)
        where = f"SCORE_AGENTE >= {int(min_score)}"
        if not incluir_sem_ajuste:
            where += " AND DECISAO_AGENTE <> 'SEM_AJUSTE_PRIORITARIO'"
        if not incluir_9282:
            where += " AND NOT (COD_COMP_ATUAL = '92' AND COD_CAUSA_ATUAL = '82')"
        return con.execute(
            f"""
            SELECT *
            FROM ({_base_query()})
            WHERE {where}
            ORDER BY
                SCORE_AGENTE DESC,
                DECISAO_AGENTE,
                PCT_DOMINANCIA_SERVICO DESC,
                QTD_RECLAMACOES DESC,
                DIC_OCORRENCIA DESC
            """
        ).fetchdf()


def resumo_agente(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "DECISAO_AGENTE",
                "COD_COMP_ATUAL",
                "COD_CAUSA_ATUAL",
                "COD_COMP_SUGERIDO",
                "COD_CAUSA_SUGERIDA",
                "INTERRUPCOES",
                "SCORE_MAX",
                "SCORE_MEDIO",
                "DIC_TOTAL",
                "RECLAMACOES",
            ]
        )

    return (
        df.groupby(
            [
                "DECISAO_AGENTE",
                "COD_COMP_ATUAL",
                "COD_CAUSA_ATUAL",
                "COD_COMP_SUGERIDO",
                "COD_CAUSA_SUGERIDA",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            INTERRUPCOES=("NUM_SEQ_INTRP", "nunique"),
            SCORE_MAX=("SCORE_AGENTE", "max"),
            SCORE_MEDIO=("SCORE_AGENTE", "mean"),
            DIC_TOTAL=("DIC_OCORRENCIA", "sum"),
            RECLAMACOES=("QTD_RECLAMACOES", "sum"),
        )
        .sort_values(["SCORE_MAX", "INTERRUPCOES", "DIC_TOTAL"], ascending=[False, False, False])
    )


def _linhas_iqs_agente(db_path: str | Path, candidatos: pd.DataFrame) -> pd.DataFrame:
    if candidatos.empty:
        return pd.DataFrame(columns=LAYOUT_IQS_COLUNAS)

    chaves = (
        candidatos[
            [
                "NUM_SEQ_INTRP",
                "COD_COMP_SUGERIDO",
                "COD_CAUSA_SUGERIDA",
                "PAR_SERVICO_SUGERIDO_VALIDO",
            ]
        ]
        .astype(str)
        .apply(lambda column: column.str.strip())
    )
    chaves = chaves[
        chaves["NUM_SEQ_INTRP"].ne("")
        & chaves["COD_COMP_SUGERIDO"].ne("")
        & chaves["COD_CAUSA_SUGERIDA"].ne("")
        & chaves["PAR_SERVICO_SUGERIDO_VALIDO"].isin({"1", "1.0", "True", "true"})
    ].drop_duplicates(subset=["NUM_SEQ_INTRP"])
    if chaves.empty:
        return pd.DataFrame(columns=LAYOUT_IQS_COLUNAS)

    with duckdb.connect(str(db_path), read_only=True) as con:
        if not _table_exists(con, "adms_iqs_export"):
            raise RuntimeError(
                "Tabela adms_iqs_export nao encontrada. Execute run.bat exportar ou run.bat tratamento antes."
            )
        con.register("agente_comp_causa_chaves", chaves[["NUM_SEQ_INTRP"]])
        base = con.execute(
            f"""
            SELECT e.{", e.".join(LAYOUT_IQS_COLUNAS)}
            FROM adms_iqs_export e
            JOIN agente_comp_causa_chaves c
              ON TRIM(CAST(e.NUM_SEQ_INTRP AS VARCHAR)) = c.NUM_SEQ_INTRP
            """
        ).fetchdf()

    if base.empty:
        return pd.DataFrame(columns=LAYOUT_IQS_COLUNAS)

    base = base.reindex(columns=LAYOUT_IQS_COLUNAS).copy()
    seq = base["NUM_SEQ_INTRP"].astype(str).str.strip()
    comp_map = chaves.set_index("NUM_SEQ_INTRP")["COD_COMP_SUGERIDO"].to_dict()
    causa_map = chaves.set_index("NUM_SEQ_INTRP")["COD_CAUSA_SUGERIDA"].to_dict()
    mask = seq.isin(comp_map)
    base.loc[mask, "COD_COMP_INTRP"] = seq.loc[mask].map(comp_map)
    base.loc[mask, "COD_CAUSA_INTRP"] = seq.loc[mask].map(causa_map)
    base.loc[mask, "VALID_POS_OPERACAO"] = "S"
    base = base.reindex(columns=LAYOUT_IQS_COLUNAS)
    validar_layout_iqs(base)
    return aplicar_formato_oficial_iqs(base)


def gerar_exportacao_agente_comp_causa(
    anomes: str = ANOMES,
    db_path: str | Path | None = None,
    raw_path: str | Path | None = None,
    min_score: int = 50,
    incluir_sem_ajuste: bool = False,
    incluir_9282: bool = False,
) -> dict[str, object]:
    detalhe = analisar_componentes_causas(
        anomes=anomes,
        db_path=db_path,
        raw_path=raw_path,
        min_score=min_score,
        incluir_sem_ajuste=incluir_sem_ajuste,
        incluir_9282=incluir_9282,
    )
    resumo = resumo_agente(detalhe)
    db_path = Path(db_path) if db_path else processed_path(anomes)
    iqs_df = _linhas_iqs_agente(db_path, detalhe)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    detalhe_path = EXPORT_DIR / f"Agente_Comp_Causa_{anomes}_{timestamp}_DETALHE.CSV"
    resumo_path = EXPORT_DIR / f"Agente_Comp_Causa_{anomes}_{timestamp}_RESUMO.CSV"
    nota_path = EXPORT_DIR / f"Agente_Comp_Causa_{anomes}_{timestamp}_NOTA.TXT"
    iqs_path = EXPORT_DIR / f"Interrupcoes_IQS_Agente_Comp_Causa_{anomes}_{timestamp}.CSV"

    detalhe.to_csv(detalhe_path, sep=";", index=False, encoding="utf-8-sig")
    resumo.to_csv(resumo_path, sep=";", index=False, encoding="utf-8-sig")
    exportar_dataframe_iqs(iqs_df, iqs_path)

    with nota_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("AGENTE COMPONENTE/CAUSA\n")
        file.write(f"ANOMES: {anomes}\n")
        file.write(f"Score minimo: {min_score}\n")
        file.write(f"Inclui 92/82: {'sim' if incluir_9282 else 'nao'}\n")
        file.write(f"Candidatos: {len(detalhe)}\n")
        file.write(f"Linhas IQS exportadas: {len(iqs_df)}\n")
        file.write(f"Grupos resumo: {len(resumo)}\n")
        file.write(f"Detalhe: {detalhe_path}\n")
        file.write(f"Resumo: {resumo_path}\n")
        file.write(f"Arquivo IQS: {iqs_path}\n")
        file.write(
            "Regra: prioriza divergencia entre componente/causa atual e par dominante dos servicos ADMS, "
            "par atual fora da referencia IQS e reclamacao forte aderente.\n"
        )

    return {
        "detalhe": detalhe_path,
        "resumo": resumo_path,
        "nota": nota_path,
        "iqs": iqs_path,
        "linhas": len(detalhe),
        "linhas_iqs": len(iqs_df),
        "grupos": len(resumo),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agente para identificar outros componentes/causas que podem precisar de ajuste."
    )
    parser.add_argument("anomes", nargs="?", default=ANOMES)
    parser.add_argument("--min-score", type=int, default=int(os.getenv("AGENTE_COMP_CAUSA_MIN_SCORE", "50")))
    parser.add_argument("--todos", action="store_true", help="Inclui registros sem ajuste prioritario.")
    parser.add_argument("--inclui-9282", action="store_true", help="Inclui o par 92/82 na varredura.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = gerar_exportacao_agente_comp_causa(
        anomes=args.anomes,
        min_score=args.min_score,
        incluir_sem_ajuste=args.todos,
        incluir_9282=args.inclui_9282,
    )
    print("AGENTE COMPONENTE/CAUSA")
    print(f"Linhas candidatas: {result['linhas']}")
    print(f"Linhas IQS: {result['linhas_iqs']}")
    print(f"Grupos no resumo: {result['grupos']}")
    print(f"Detalhe: {result['detalhe']}")
    print(f"Resumo: {result['resumo']}")
    print(f"Nota: {result['nota']}")
    print(f"Arquivo IQS: {result['iqs']}")


if __name__ == "__main__":
    main()

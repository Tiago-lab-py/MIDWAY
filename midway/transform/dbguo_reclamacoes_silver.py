from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")

BASE_DIR = Path("data")
RAW_DUCKDB_PATH = BASE_DIR / "raw" / f"dbguo_raw_{ANOMES}.duckdb"
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
MARTS_DIR = BASE_DIR / "marts"

TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")
RAW_SCHEMA = "dbguo_raw"
RAW_TABLE = "raw_dbguo_reclamacoes"


def table_exists(con, table_name: str, schema: str = "main") -> bool:
    information_schema = (
        "information_schema.tables"
        if schema == "main"
        else f"{schema}.information_schema.tables"
    )

    return (
        con.execute(
            f"""
            SELECT COUNT(*)
            FROM {information_schema}
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


def table_columns(con, table_name: str, schema: str = "main") -> list[str]:
    information_schema = (
        "information_schema.columns"
        if schema == "main"
        else f"{schema}.information_schema.columns"
    )

    return [
        row[0]
        for row in con.execute(
            f"""
            SELECT column_name
            FROM {information_schema}
            WHERE table_schema = 'main'
              AND table_name = ?
            ORDER BY ordinal_position
            """,
            [table_name],
        ).fetchall()
    ]


def first_existing(columns: list[str], candidates: list[str]) -> str | None:
    mapping = {col.upper(): col for col in columns}
    for candidate in candidates:
        if candidate.upper() in mapping:
            return mapping[candidate.upper()]
    return None


def attach_dbguo_raw(con) -> str:
    if not RAW_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB raw DBGUO nao encontrado: {RAW_DUCKDB_PATH}")

    try:
        con.execute(f"ATTACH '{RAW_DUCKDB_PATH.as_posix()}' AS {RAW_SCHEMA} (READ_ONLY)")
    except duckdb.BinderException:
        pass

    return RAW_SCHEMA


def criar_silver_reclamacoes(con):
    raw_schema = attach_dbguo_raw(con)

    if not table_exists(con, RAW_TABLE, raw_schema):
        tabelas = con.execute(
            f"""
            SELECT table_name
            FROM {raw_schema}.information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchdf()["table_name"].tolist()
        raise RuntimeError(
            f"Tabela {raw_schema}.{RAW_TABLE} nao encontrada. Tabelas encontradas: {tabelas}"
        )

    if not table_exists(con, "gold_apuracao_uc"):
        raise RuntimeError("Tabela gold_apuracao_uc nao encontrada. Execute run.bat apuracao_parcial.")

    raw_cols = table_columns(con, RAW_TABLE, raw_schema)

    col_uc = first_existing(
        raw_cols,
        [
            "UC",
            "NUM_UC",
            "NUM_UC_RECLAMACAO",
            "NUM_UC_CONSUMIDORA",
            "UNIDADE_CONSUMIDORA",
        ],
    )
    col_data = first_existing(
        raw_cols,
        [
            "DTHR_RECLAMACAO",
            "DATA_HORA_RECLAMACAO",
            "DATA_RECLAMACAO",
            "DTHR_CRIACAO",
            "DATA_ABERTURA",
            "DTHR_ABERTURA",
            "CRIADO_EM",
            "DTHR_SOLICITACAO",
        ],
    )
    col_id = first_existing(
        raw_cols,
        [
            "ID_RECLAMACAO",
            "NUM_RECLAMACAO",
            "PROTOCOLO",
            "NUM_PROTOCOLO",
            "ID",
            "PID",
        ],
    )

    if not col_uc:
        raise RuntimeError(f"Nao encontrei coluna de UC no raw DBGUO. Colunas: {raw_cols}")

    if not col_data:
        raise RuntimeError(f"Nao encontrei coluna de data/hora no raw DBGUO. Colunas: {raw_cols}")

    id_expr = (
        f'NULLIF(TRIM(CAST(r."{col_id}" AS VARCHAR)), \'\')'
        if col_id
        else "CAST(ROW_NUMBER() OVER () AS VARCHAR)"
    )

    apuracao_cols = table_columns(con, "gold_apuracao_uc")
    alim_expr = "NULL"
    oper_chv_expr = "NULL"
    geo_chv_expr = "NULL"
    if "ALIM_INTRP" in {col.upper() for col in apuracao_cols}:
        alim_expr = "NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')"
    if "NUM_OPER_CHV_INTRP" in {col.upper() for col in apuracao_cols}:
        oper_chv_expr = "NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')"
    if "NUM_GEO_CHV_INTRP" in {col.upper() for col in apuracao_cols}:
        geo_chv_expr = "NULLIF(TRIM(CAST(NUM_GEO_CHV_INTRP AS VARCHAR)), '')"

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_dbguo_reclamacoes_candidatas AS
        WITH reclamacoes AS (
            SELECT
                {id_expr} AS ID_RECLAMACAO,
                NULLIF(TRIM(CAST(r."{col_uc}" AS VARCHAR)), '') AS UC,
                TRY_CAST(r."{col_data}" AS TIMESTAMP) AS DTHR_RECLAMACAO,
                r.*
            FROM {raw_schema}.{RAW_TABLE} r
        ),
        eventos AS (
            SELECT
                NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS UC,
                NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') AS NUM_OCORRENCIA_ADMS,
                NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') AS NUM_SEQ_INTRP,
                NULLIF(TRIM(CAST(NUM_INTRP_UCI AS VARCHAR)), '') AS NUM_INTRP_UCI,
                NULLIF(TRIM(CAST(NUM_POSTO_UCI AS VARCHAR)), '') AS NUM_POSTO_UCI,
                NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '') AS CONJUNTO,
                {alim_expr} AS ALIM_INTRP,
                {oper_chv_expr} AS NUM_OPER_CHV_INTRP,
                {geo_chv_expr} AS NUM_GEO_CHV_INTRP,
                NULLIF(TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)), '') AS TIPO_PROTOC_JUSTIF_UCI,
                NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), '') AS COD_CAUSA_INTRP,
                NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), '') AS COD_COMP_INTRP,
                TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) AS INICIO_INTERRUPCAO_UC,
                TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) AS FIM_INTERRUPCAO,
                COALESCE(TRY_CAST(DURACAO_HORA AS DOUBLE), 0) AS DURACAO_HORA,
                COALESCE(TRY_CAST(CI_LIQUIDO AS DOUBLE), 0) AS CI_LIQUIDO,
                COALESCE(TRY_CAST(CHI_LIQUIDO AS DOUBLE), 0) AS CHI_LIQUIDO
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
              AND DTHR_INICIO_INTRP_UC IS NOT NULL
              AND DATA_HORA_FIM_INTRP IS NOT NULL
        )
        SELECT
            r.ID_RECLAMACAO,
            r.UC,
            r.DTHR_RECLAMACAO,

            e.NUM_OCORRENCIA_ADMS,
            e.NUM_SEQ_INTRP,
            e.NUM_INTRP_UCI,
            e.NUM_POSTO_UCI,
            e.CONJUNTO,
            e.ALIM_INTRP,
            e.NUM_OPER_CHV_INTRP,
            e.NUM_GEO_CHV_INTRP,
            e.TIPO_PROTOC_JUSTIF_UCI,
            e.COD_CAUSA_INTRP,
            e.COD_COMP_INTRP,
            e.INICIO_INTERRUPCAO_UC,
            e.FIM_INTERRUPCAO,
            e.DURACAO_HORA,
            e.CI_LIQUIDO,
            e.CHI_LIQUIDO,

            CASE
                WHEN r.DTHR_RECLAMACAO BETWEEN e.INICIO_INTERRUPCAO_UC AND e.FIM_INTERRUPCAO
                THEN 0
                WHEN r.DTHR_RECLAMACAO < e.INICIO_INTERRUPCAO_UC
                THEN ABS(DATE_DIFF('minute', r.DTHR_RECLAMACAO, e.INICIO_INTERRUPCAO_UC))
                ELSE ABS(DATE_DIFF('minute', e.FIM_INTERRUPCAO, r.DTHR_RECLAMACAO))
            END AS DISTANCIA_MINUTOS,

            CASE
                WHEN r.DTHR_RECLAMACAO BETWEEN e.INICIO_INTERRUPCAO_UC AND e.FIM_INTERRUPCAO
                THEN 'DURANTE_INTERRUPCAO'
                WHEN r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO
                THEN 'APOS_INTERRUPCAO'
                WHEN r.DTHR_RECLAMACAO < e.INICIO_INTERRUPCAO_UC
                THEN 'ANTES_INTERRUPCAO'
                ELSE 'INDEFINIDO'
            END AS POSICAO_RECLAMACAO,

            CASE
                WHEN r.DTHR_RECLAMACAO BETWEEN e.INICIO_INTERRUPCAO_UC AND e.FIM_INTERRUPCAO
                THEN 100
                WHEN r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO
                 AND DATE_DIFF('minute', e.FIM_INTERRUPCAO, r.DTHR_RECLAMACAO) BETWEEN 0 AND 60
                THEN 90
                WHEN r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO
                 AND DATE_DIFF('minute', e.FIM_INTERRUPCAO, r.DTHR_RECLAMACAO) BETWEEN 61 AND 360
                THEN 80
                WHEN r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO
                 AND DATE_DIFF('minute', e.FIM_INTERRUPCAO, r.DTHR_RECLAMACAO) BETWEEN 361 AND 1440
                THEN 65
                WHEN r.DTHR_RECLAMACAO < e.INICIO_INTERRUPCAO_UC
                 AND DATE_DIFF('minute', r.DTHR_RECLAMACAO, e.INICIO_INTERRUPCAO_UC) BETWEEN 0 AND 120
                THEN 50
                ELSE 0
            END AS SCORE_VINCULO_RECLAMACAO
        FROM reclamacoes r
        JOIN eventos e
          ON e.UC = r.UC
         AND r.DTHR_RECLAMACAO >= e.INICIO_INTERRUPCAO_UC - INTERVAL '2 hours'
         AND r.DTHR_RECLAMACAO <= e.FIM_INTERRUPCAO + INTERVAL '24 hours'
        WHERE r.UC IS NOT NULL
          AND r.DTHR_RECLAMACAO IS NOT NULL
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE silver_dbguo_reclamacoes AS
        SELECT
            * EXCLUDE (RN),
            CASE
                WHEN SCORE_VINCULO_RECLAMACAO >= 100 THEN 'VINCULO_FORTE_DURANTE_INTERRUPCAO'
                WHEN SCORE_VINCULO_RECLAMACAO >= 80 THEN 'VINCULO_FORTE_APOS_INTERRUPCAO'
                WHEN SCORE_VINCULO_RECLAMACAO >= 60 THEN 'VINCULO_PROVAVEL'
                WHEN SCORE_VINCULO_RECLAMACAO >= 50 THEN 'VINCULO_FRACO_ANTES_INTERRUPCAO'
                ELSE 'SEM_OCORRENCIA_PROVAVEL'
            END AS CLASSIFICACAO_VINCULO_RECLAMACAO
        FROM (
            SELECT
                *,
                ROW_NUMBER() OVER (
                    PARTITION BY ID_RECLAMACAO
                    ORDER BY
                        SCORE_VINCULO_RECLAMACAO DESC,
                        DISTANCIA_MINUTOS ASC,
                        INICIO_INTERRUPCAO_UC DESC
                ) AS RN
            FROM silver_dbguo_reclamacoes_candidatas
        )
        WHERE RN = 1
        """
    )

    con.execute("CREATE INDEX IF NOT EXISTS idx_silver_dbguo_reclamacoes_uc ON silver_dbguo_reclamacoes(UC)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_silver_dbguo_reclamacoes_ocorrencia ON silver_dbguo_reclamacoes(NUM_OCORRENCIA_ADMS)")


def exportar_resumo(con):
    MARTS_DIR.mkdir(parents=True, exist_ok=True)

    resumo_path = MARTS_DIR / f"Silver_DBGUO_Reclamacoes_{ANOMES}_{TIMESTAMP}_RESUMO.TXT"

    row = con.execute(
        """
        SELECT
            COUNT(*) AS TOTAL,
            COUNT(DISTINCT UC) AS UCS,
            COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS OCORRENCIAS,
            SUM(CASE WHEN CLASSIFICACAO_VINCULO_RECLAMACAO <> 'SEM_OCORRENCIA_PROVAVEL' THEN 1 ELSE 0 END) AS COM_VINCULO
        FROM silver_dbguo_reclamacoes
        """
    ).fetchone()

    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("SILVER DBGUO RECLAMACOES\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write("Tabela: silver_dbguo_reclamacoes\n")
        arquivo.write(f"Total: {row[0]}\n")
        arquivo.write(f"UCs: {row[1]}\n")
        arquivo.write(f"Ocorrencias: {row[2]}\n")
        arquivo.write(f"Com vinculo: {row[3]}\n")

    print("silver_dbguo_reclamacoes criada.")
    print(f"Resumo: {resumo_path}")


def main():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    try:
        criar_silver_reclamacoes(con)
        exportar_resumo(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()

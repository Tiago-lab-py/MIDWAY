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
    if schema == "main":
        sql = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = ?
        """
        return con.execute(sql, [table_name]).fetchone()[0] > 0

    sql = """
        SELECT COUNT(*)
        FROM duckdb_tables()
        WHERE database_name = ?
          AND schema_name = 'main'
          AND table_name = ?
    """
    return con.execute(sql, [schema, table_name]).fetchone()[0] > 0


def table_columns(con, table_name: str, schema: str = "main") -> list[str]:
    if schema == "main":
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = ?
            ORDER BY ordinal_position
        """
        return [row[0] for row in con.execute(sql, [table_name]).fetchall()]

    sql = """
        SELECT column_name
        FROM duckdb_columns()
        WHERE database_name = ?
          AND schema_name = 'main'
          AND table_name = ?
        ORDER BY column_index
    """
    return [row[0] for row in con.execute(sql, [schema, table_name]).fetchall()]


def listar_tabelas(con, schema: str = "main") -> list[str]:
    if schema == "main":
        return [
            row[0]
            for row in con.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                ORDER BY table_name
                """
            ).fetchall()
        ]

    return [
        row[0]
        for row in con.execute(
            """
            SELECT table_name
            FROM duckdb_tables()
            WHERE database_name = ?
              AND schema_name = 'main'
            ORDER BY table_name
            """,
            [schema],
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
        tabelas = listar_tabelas(con, raw_schema)
        raise RuntimeError(
            f"Tabela {raw_schema}.{RAW_TABLE} nao encontrada. Tabelas encontradas: {tabelas}"
        )

    if not table_exists(con, "gold_apuracao_uc"):
        raise RuntimeError("Tabela gold_apuracao_uc nao encontrada. Execute run.bat apuracao_parcial.")

    raw_cols = table_columns(con, RAW_TABLE, raw_schema)
    col_uc = first_existing(
        raw_cols,
        ["UC", "NUM_UC", "NUM_UC_RECLAMACAO", "NUM_UC_CONSUMIDORA", "UNIDADE_CONSUMIDORA"],
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
        ["ID_RECLAMACAO", "NUM_RECLAMACAO", "PROTOCOLO", "NUM_PROTOCOLO", "ID", "PID"],
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
    apuracao_cols_upper = {col.upper() for col in apuracao_cols}
    alim_expr = "NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')" if "ALIM_INTRP" in apuracao_cols_upper else "NULL"
    oper_chv_expr = "NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')" if "NUM_OPER_CHV_INTRP" in apuracao_cols_upper else "NULL"
    geo_chv_expr = "NULLIF(TRIM(CAST(NUM_GEO_CHV_INTRP AS VARCHAR)), '')" if "NUM_GEO_CHV_INTRP" in apuracao_cols_upper else "NULL"

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_dbguo_reclamacoes_candidatas AS
        WITH reclamacoes AS (
            SELECT
                {id_expr} AS ID_RECLAMACAO,
                NULLIF(TRIM(CAST(r."{col_uc}" AS VARCHAR)), '') AS UC,
                TRY_CAST(r."{col_data}" AS TIMESTAMP) AS DTHR_RECLAMACAO
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
            COALESCE(e.DURACAO_HORA, 0) AS DURACAO_HORA,
            COALESCE(e.CI_LIQUIDO, 0) AS CI_LIQUIDO,
            COALESCE(e.CHI_LIQUIDO, 0) AS CHI_LIQUIDO,
            CASE
                WHEN e.NUM_SEQ_INTRP IS NULL THEN NULL
                WHEN r.DTHR_RECLAMACAO BETWEEN e.INICIO_INTERRUPCAO_UC AND e.FIM_INTERRUPCAO THEN 0
                WHEN r.DTHR_RECLAMACAO < e.INICIO_INTERRUPCAO_UC THEN ABS(DATE_DIFF('minute', r.DTHR_RECLAMACAO, e.INICIO_INTERRUPCAO_UC))
                ELSE ABS(DATE_DIFF('minute', e.FIM_INTERRUPCAO, r.DTHR_RECLAMACAO))
            END AS DISTANCIA_MINUTOS,
            CASE
                WHEN e.NUM_SEQ_INTRP IS NULL THEN 'SEM_OCORRENCIA_PROVAVEL'
                WHEN r.DTHR_RECLAMACAO BETWEEN e.INICIO_INTERRUPCAO_UC AND e.FIM_INTERRUPCAO THEN 'DURANTE_INTERRUPCAO'
                WHEN r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO THEN 'APOS_INTERRUPCAO'
                WHEN r.DTHR_RECLAMACAO < e.INICIO_INTERRUPCAO_UC THEN 'ANTES_INTERRUPCAO'
                ELSE 'INDEFINIDO'
            END AS POSICAO_RECLAMACAO,
            CASE
                WHEN e.NUM_SEQ_INTRP IS NULL THEN 0
                WHEN r.DTHR_RECLAMACAO BETWEEN e.INICIO_INTERRUPCAO_UC AND e.FIM_INTERRUPCAO THEN 100
                WHEN r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO
                 AND DATE_DIFF('minute', e.FIM_INTERRUPCAO, r.DTHR_RECLAMACAO) BETWEEN 0 AND 60 THEN 90
                WHEN r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO
                 AND DATE_DIFF('minute', e.FIM_INTERRUPCAO, r.DTHR_RECLAMACAO) BETWEEN 61 AND 360 THEN 80
                WHEN r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO
                 AND DATE_DIFF('minute', e.FIM_INTERRUPCAO, r.DTHR_RECLAMACAO) BETWEEN 361 AND 1440 THEN 65
                WHEN r.DTHR_RECLAMACAO < e.INICIO_INTERRUPCAO_UC
                 AND DATE_DIFF('minute', r.DTHR_RECLAMACAO, e.INICIO_INTERRUPCAO_UC) BETWEEN 0 AND 120 THEN 50
                ELSE 0
            END AS SCORE_VINCULO_RECLAMACAO
        FROM reclamacoes r
        LEFT JOIN eventos e
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
                        COALESCE(DISTANCIA_MINUTOS, 999999999) ASC,
                        INICIO_INTERRUPCAO_UC DESC NULLS LAST
                ) AS RN
            FROM silver_dbguo_reclamacoes_candidatas
        )
        WHERE RN = 1
        """
    )

    con.execute("CREATE INDEX IF NOT EXISTS idx_silver_dbguo_reclamacoes_uc ON silver_dbguo_reclamacoes(UC)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_silver_dbguo_reclamacoes_ocorrencia ON silver_dbguo_reclamacoes(NUM_OCORRENCIA_ADMS)")


def criar_gold_reclamacoes(con):
    if not table_exists(con, "silver_dbguo_reclamacoes"):
        raise RuntimeError("Tabela silver_dbguo_reclamacoes nao encontrada.")

    apuracao_cols = table_columns(con, "gold_apuracao_uc")
    valid_pos_col = first_existing(apuracao_cols, ["VALID_POS_OPERACAO"])
    valid_pos_expr = (
        "MAX(CASE WHEN UPPER(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR))) = 'S' THEN 'S' ELSE 'N' END)"
        if valid_pos_col
        else "'N'"
    )

    if table_exists(con, "gold_ressarcimento_prodist"):
        ressarcimento_cte = """
            SELECT
                NULLIF(TRIM(CAST(UC AS VARCHAR)), '') AS UC,
                COALESCE(TRY_CAST(COMP_TOTAL_PRODIST AS DOUBLE), 0) AS COMP_TOTAL_PRODIST_UC
            FROM gold_ressarcimento_prodist
            WHERE NULLIF(TRIM(CAST(UC AS VARCHAR)), '') IS NOT NULL
        """
    else:
        ressarcimento_cte = """
            SELECT CAST(NULL AS VARCHAR) AS UC, CAST(0 AS DOUBLE) AS COMP_TOTAL_PRODIST_UC
            WHERE FALSE
        """

    con.execute(
        f"""
        CREATE OR REPLACE TABLE gold_reclamacao_uc_vinculada AS
        WITH status_ocorrencia AS (
            SELECT
                NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') AS NUM_OCORRENCIA_ADMS,
                {valid_pos_expr} AS VALID_POS_OPERACAO,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_APURAVEIS_OCORRENCIA,
                SUM(COALESCE(TRY_CAST(CI_LIQUIDO AS DOUBLE), 0)) AS FIC_OCORRENCIA,
                SUM(COALESCE(TRY_CAST(CHI_LIQUIDO AS DOUBLE), 0)) AS DIC_OCORRENCIA
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')
        ),
        ressarcimento_uc AS ({ressarcimento_cte})
        SELECT
            s.ID_RECLAMACAO,
            s.UC,
            CAST(s.DTHR_RECLAMACAO AS DATE) AS DATA_RECLAMACAO,
            s.DTHR_RECLAMACAO,
            s.NUM_OCORRENCIA_ADMS,
            s.NUM_SEQ_INTRP,
            s.NUM_INTRP_UCI,
            s.NUM_POSTO_UCI,
            s.CONJUNTO,
            s.ALIM_INTRP,
            s.NUM_OPER_CHV_INTRP,
            s.NUM_GEO_CHV_INTRP,
            s.TIPO_PROTOC_JUSTIF_UCI,
            s.COD_CAUSA_INTRP,
            s.COD_COMP_INTRP,
            s.INICIO_INTERRUPCAO_UC,
            s.FIM_INTERRUPCAO,
            s.DURACAO_HORA,
            s.CI_LIQUIDO,
            s.CHI_LIQUIDO,
            s.DISTANCIA_MINUTOS,
            s.POSICAO_RECLAMACAO,
            s.SCORE_VINCULO_RECLAMACAO,
            s.CLASSIFICACAO_VINCULO_RECLAMACAO,
            CASE WHEN s.CLASSIFICACAO_VINCULO_RECLAMACAO <> 'SEM_OCORRENCIA_PROVAVEL' THEN 'S' ELSE 'N' END AS TEM_OCORRENCIA_PROVAVEL,
            COALESCE(o.VALID_POS_OPERACAO, 'N') AS VALID_POS_OPERACAO,
            COALESCE(o.UCS_APURAVEIS_OCORRENCIA, 0) AS UCS_APURAVEIS_OCORRENCIA,
            COALESCE(o.FIC_OCORRENCIA, 0) AS FIC_OCORRENCIA,
            COALESCE(o.DIC_OCORRENCIA, 0) AS DIC_OCORRENCIA,
            COALESCE(r.COMP_TOTAL_PRODIST_UC, 0) AS COMP_TOTAL_PRODIST_UC,
            CASE
                WHEN COALESCE(o.VALID_POS_OPERACAO, 'N') = 'S' THEN 'OCORRENCIA_VALIDADA_POS'
                WHEN s.CLASSIFICACAO_VINCULO_RECLAMACAO = 'SEM_OCORRENCIA_PROVAVEL' THEN 'RECLAMACAO_SEM_OCORRENCIA_PROVAVEL'
                WHEN s.SCORE_VINCULO_RECLAMACAO >= 80 THEN 'VINCULO_FORTE'
                WHEN s.SCORE_VINCULO_RECLAMACAO >= 60 THEN 'VINCULO_PROVAVEL'
                WHEN s.SCORE_VINCULO_RECLAMACAO >= 50 THEN 'VINCULO_FRACO'
                ELSE 'RECLAMACAO_SEM_OCORRENCIA_PROVAVEL'
            END AS STATUS_AVALIACAO_RECLAMACAO
        FROM silver_dbguo_reclamacoes s
        LEFT JOIN status_ocorrencia o ON o.NUM_OCORRENCIA_ADMS = s.NUM_OCORRENCIA_ADMS
        LEFT JOIN ressarcimento_uc r ON r.UC = s.UC
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_reclamacao_uc_resumo AS
        SELECT
            UC,
            MIN(DATA_RECLAMACAO) AS PRIMEIRA_DATA_RECLAMACAO,
            MAX(DATA_RECLAMACAO) AS ULTIMA_DATA_RECLAMACAO,
            COUNT(*) AS QTD_RECLAMACOES,
            COUNT(DISTINCT ID_RECLAMACAO) AS QTD_RECLAMACOES_DISTINTAS,
            COUNT(DISTINCT NUM_OCORRENCIA_ADMS) FILTER (WHERE TEM_OCORRENCIA_PROVAVEL = 'S') AS QTD_OCORRENCIAS_PROVAVEIS,
            SUM(CASE WHEN TEM_OCORRENCIA_PROVAVEL = 'S' THEN 1 ELSE 0 END) AS QTD_COM_OCORRENCIA_PROVAVEL,
            SUM(CASE WHEN TEM_OCORRENCIA_PROVAVEL = 'N' THEN 1 ELSE 0 END) AS QTD_SEM_OCORRENCIA_PROVAVEL,
            SUM(CASE WHEN VALID_POS_OPERACAO = 'S' THEN 1 ELSE 0 END) AS QTD_RECLAMACOES_OCORRENCIA_VALIDADA_POS,
            MAX(SCORE_VINCULO_RECLAMACAO) AS MAX_SCORE_VINCULO_RECLAMACAO,
            MIN(DISTANCIA_MINUTOS) AS MENOR_DISTANCIA_MINUTOS,
            MAX(COALESCE(COMP_TOTAL_PRODIST_UC, 0)) AS COMP_TOTAL_PRODIST_UC_REFERENCIA
        FROM gold_reclamacao_uc_vinculada
        GROUP BY UC
        """
    )

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_reclamacao_ocorrencia_resumo AS
        SELECT
            NUM_OCORRENCIA_ADMS,
            MIN(DATA_RECLAMACAO) AS PRIMEIRA_DATA_RECLAMACAO,
            MAX(DATA_RECLAMACAO) AS ULTIMA_DATA_RECLAMACAO,
            COUNT(*) AS QTD_RECLAMACOES,
            COUNT(DISTINCT UC) AS QTD_UCS_RECLAMANTES,
            MAX(UCS_APURAVEIS_OCORRENCIA) AS UCS_APURAVEIS_OCORRENCIA,
            MAX(FIC_OCORRENCIA) AS FIC_OCORRENCIA,
            MAX(DIC_OCORRENCIA) AS DIC_OCORRENCIA,
            MAX(VALID_POS_OPERACAO) AS VALID_POS_OPERACAO,
            MAX(SCORE_VINCULO_RECLAMACAO) AS MAX_SCORE_VINCULO_RECLAMACAO,
            MIN(DISTANCIA_MINUTOS) AS MENOR_DISTANCIA_MINUTOS
        FROM gold_reclamacao_uc_vinculada
        WHERE TEM_OCORRENCIA_PROVAVEL = 'S'
          AND NUM_OCORRENCIA_ADMS IS NOT NULL
        GROUP BY NUM_OCORRENCIA_ADMS
        """
    )

    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_reclamacao_uc_vinculada_uc ON gold_reclamacao_uc_vinculada(UC)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_reclamacao_uc_vinculada_ocorrencia ON gold_reclamacao_uc_vinculada(NUM_OCORRENCIA_ADMS)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_reclamacao_uc_resumo_uc ON gold_reclamacao_uc_resumo(UC)")


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
    gold_row = con.execute(
        """
        SELECT
            COUNT(*) AS TOTAL_GOLD,
            COUNT(DISTINCT UC) AS UCS_GOLD,
            SUM(CASE WHEN TEM_OCORRENCIA_PROVAVEL = 'S' THEN 1 ELSE 0 END) AS COM_OCORRENCIA_PROVAVEL,
            SUM(CASE WHEN VALID_POS_OPERACAO = 'S' THEN 1 ELSE 0 END) AS OCORRENCIA_VALIDADA_POS
        FROM gold_reclamacao_uc_vinculada
        """
    ).fetchone()

    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("SILVER/GOLD DBGUO RECLAMACOES\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write("Tabela silver: silver_dbguo_reclamacoes\n")
        arquivo.write("Tabela gold detalhe: gold_reclamacao_uc_vinculada\n")
        arquivo.write("Tabela gold UC: gold_reclamacao_uc_resumo\n")
        arquivo.write("Tabela gold ocorrencia: gold_reclamacao_ocorrencia_resumo\n")
        arquivo.write(f"Total silver: {row[0]}\n")
        arquivo.write(f"UCs silver: {row[1]}\n")
        arquivo.write(f"Ocorrencias silver: {row[2]}\n")
        arquivo.write(f"Com vinculo silver: {row[3]}\n")
        arquivo.write(f"Total gold: {gold_row[0]}\n")
        arquivo.write(f"UCs gold: {gold_row[1]}\n")
        arquivo.write(f"Com ocorrencia provavel gold: {gold_row[2]}\n")
        arquivo.write(f"Ocorrencia validada pos gold: {gold_row[3]}\n")

    print("silver_dbguo_reclamacoes criada.")
    print("gold_reclamacao_uc_vinculada criada.")
    print("gold_reclamacao_uc_resumo criada.")
    print("gold_reclamacao_ocorrencia_resumo criada.")
    print(f"Resumo: {resumo_path}")


def main():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    try:
        criar_silver_reclamacoes(con)
        criar_gold_reclamacoes(con)
        exportar_resumo(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()

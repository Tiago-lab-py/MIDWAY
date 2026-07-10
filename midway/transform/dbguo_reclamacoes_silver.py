from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
INPUT_DIR = BASE_DIR / "input"
RAW_DUCKDB_PATH = BASE_DIR / "raw" / f"dbguo_raw_{ANOMES}.duckdb"
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
MARTS_DIR = BASE_DIR / "marts"
TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")
RAW_SCHEMA = "dbguo_raw"
RAW_TABLE = "raw_dbguo_reclamacoes"
CAUSA_CSV_PATH = Path(os.getenv("IQS_CAUSA_CSV", str(INPUT_DIR / "causa.csv")))
COMPONENTE_CSV_PATH = Path(os.getenv("IQS_COMPONENTE_CSV", str(INPUT_DIR / "componente.csv")))


def sql_literal(valor) -> str:
    return "'" + str(valor).replace("\\", "/").replace("'", "''") + "'"


def janela_reclamacoes_anomes() -> tuple[str, str]:
    ano = int(ANOMES[:4])
    mes = int(ANOMES[4:6])
    inicio = datetime(ano, mes, 1)
    if mes == 12:
        proximo_mes = datetime(ano + 1, 1, 1)
    else:
        proximo_mes = datetime(ano, mes + 1, 1)

    inicio_janela = inicio - timedelta(days=2)
    fim_janela = proximo_mes + timedelta(days=2)
    return inicio_janela.strftime("%Y-%m-%d %H:%M:%S"), fim_janela.strftime("%Y-%m-%d %H:%M:%S")


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


def column_text_expr(columns: list[str], column_name: str, alias: str | None = None) -> str:
    actual = first_existing(columns, [column_name])
    if not actual:
        return "CAST(NULL AS VARCHAR)"
    prefix = f'{alias}.' if alias else ""
    return f'NULLIF(TRIM(CAST({prefix}"{actual}" AS VARCHAR)), \'\')'


def attach_dbguo_raw(con) -> str:
    if not RAW_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB raw DBGUO nao encontrado: {RAW_DUCKDB_PATH}")

    try:
        con.execute(f"ATTACH '{RAW_DUCKDB_PATH.as_posix()}' AS {RAW_SCHEMA} (READ_ONLY)")
    except duckdb.BinderException:
        pass

    return RAW_SCHEMA


def criar_referencias_iqs(con):
    if CAUSA_CSV_PATH.exists():
        con.execute(
            f"""
            CREATE OR REPLACE TABLE ref_iqs_causa AS
            SELECT DISTINCT
                NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), '') AS COD_CAUSA,
                NULLIF(TRIM(CAST(DESC_CAUSA AS VARCHAR)), '') AS DESC_CAUSA
            FROM read_csv_auto({sql_literal(CAUSA_CSV_PATH.as_posix())}, header = true, all_varchar = true)
            WHERE NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), '') IS NOT NULL
            """
        )
    else:
        con.execute(
            """
            CREATE OR REPLACE TABLE ref_iqs_causa AS
            SELECT CAST(NULL AS VARCHAR) AS COD_CAUSA, CAST(NULL AS VARCHAR) AS DESC_CAUSA
            WHERE FALSE
            """
        )

    if COMPONENTE_CSV_PATH.exists():
        con.execute(
            f"""
            CREATE OR REPLACE TABLE ref_iqs_componente AS
            SELECT DISTINCT
                NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') AS COD_COMP,
                NULLIF(TRIM(CAST(DESC_COMP AS VARCHAR)), '') AS DESC_COMP
            FROM read_csv_auto({sql_literal(COMPONENTE_CSV_PATH.as_posix())}, header = true, all_varchar = true)
            WHERE NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') IS NOT NULL
            """
        )
    else:
        con.execute(
            """
            CREATE OR REPLACE TABLE ref_iqs_componente AS
            SELECT CAST(NULL AS VARCHAR) AS COD_COMP, CAST(NULL AS VARCHAR) AS DESC_COMP
            WHERE FALSE
            """
        )


def criar_silver_reclamacoes(con):
    raw_schema = attach_dbguo_raw(con)
    inicio_janela_reclamacoes, fim_janela_reclamacoes = janela_reclamacoes_anomes()

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
    col_reclamacao = first_existing(
        raw_cols,
        ["RECLAMACAO", "DESC_RECLAMACAO", "DESCRICAO_RECLAMACAO", "TEXTO_RECLAMACAO"],
    )
    col_retorno = first_existing(
        raw_cols,
        ["INFORMACAO_RETORNO", "INFO_RETORNO", "RETORNO", "DESCRICAO_RETORNO"],
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
    reclamacao_expr = (
        f'NULLIF(TRIM(CAST(r."{col_reclamacao}" AS VARCHAR)), \'\')'
        if col_reclamacao
        else "CAST(NULL AS VARCHAR)"
    )
    retorno_expr = (
        f'NULLIF(TRIM(CAST(r."{col_retorno}" AS VARCHAR)), \'\')'
        if col_retorno
        else "CAST(NULL AS VARCHAR)"
    )

    apuracao_cols = table_columns(con, "gold_apuracao_uc")
    apuracao_alim_expr = column_text_expr(apuracao_cols, "ALIM_INTRP")
    apuracao_oper_chv_expr = column_text_expr(apuracao_cols, "NUM_OPER_CHV_INTRP")
    apuracao_geo_chv_expr = column_text_expr(apuracao_cols, "NUM_GEO_CHV_INTRP")

    tratada_cols = table_columns(con, "gold_interrupcao_tratada") if table_exists(con, "gold_interrupcao_tratada") else []
    tratada_tem_chaves = all(
        first_existing(tratada_cols, [col])
        for col in ["NUM_OCORRENCIA_ADMS", "NUM_SEQ_INTRP", "NUM_INTRP_UCI"]
    )
    tratada_alim_expr = column_text_expr(tratada_cols, "ALIM_INTRP")
    tratada_oper_chv_expr = column_text_expr(tratada_cols, "NUM_OPER_CHV_INTRP")
    tratada_geo_chv_expr = column_text_expr(tratada_cols, "NUM_GEO_CHV_INTRP")

    if tratada_tem_chaves:
        interrupcao_meta_cte = f"""
        interrupcao_meta AS (
            SELECT
                NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') AS NUM_OCORRENCIA_ADMS,
                NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') AS NUM_SEQ_INTRP,
                NULLIF(TRIM(CAST(NUM_INTRP_UCI AS VARCHAR)), '') AS NUM_INTRP_UCI,
                MAX({tratada_alim_expr}) AS ALIM_INTRP_META,
                MAX({tratada_oper_chv_expr}) AS NUM_OPER_CHV_INTRP_META,
                MAX({tratada_geo_chv_expr}) AS NUM_GEO_CHV_INTRP_META
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(NUM_INTRP_UCI AS VARCHAR)), '') IS NOT NULL
            GROUP BY
                NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), ''),
                NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ''),
                NULLIF(TRIM(CAST(NUM_INTRP_UCI AS VARCHAR)), '')
        ),
        """
    else:
        interrupcao_meta_cte = """
        interrupcao_meta AS (
            SELECT
                CAST(NULL AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(NULL AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(NULL AS VARCHAR) AS NUM_INTRP_UCI,
                CAST(NULL AS VARCHAR) AS ALIM_INTRP_META,
                CAST(NULL AS VARCHAR) AS NUM_OPER_CHV_INTRP_META,
                CAST(NULL AS VARCHAR) AS NUM_GEO_CHV_INTRP_META
            WHERE FALSE
        ),
        """

    con.execute(
        f"""
        CREATE OR REPLACE TABLE silver_dbguo_reclamacoes_candidatas AS
        WITH reclamacoes AS (
            SELECT
                {id_expr} AS ID_RECLAMACAO,
                NULLIF(TRIM(CAST(r."{col_uc}" AS VARCHAR)), '') AS UC,
                TRY_CAST(r."{col_data}" AS TIMESTAMP) AS DTHR_RECLAMACAO,
                {reclamacao_expr} AS TEXTO_RECLAMACAO,
                {retorno_expr} AS TEXTO_RETORNO
            FROM {raw_schema}.{RAW_TABLE} r
            WHERE TRY_CAST(r."{col_data}" AS TIMESTAMP) >= TIMESTAMP '{inicio_janela_reclamacoes}'
              AND TRY_CAST(r."{col_data}" AS TIMESTAMP) < TIMESTAMP '{fim_janela_reclamacoes}'
        ),
        reclamacoes_classificadas AS (
            SELECT
                *,
                CASE
                    WHEN UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%OSCIL%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%PISC%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%TENSAO%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%TENSÃO%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%MEIA FASE%'
                        THEN 'OSCILACAO_TENSAO'
                    WHEN UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%FALTA DE ENERGIA%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%FALTA ENERGIA%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%SEM ENERGIA%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%CHAVE CAIDA%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%DESLIG%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%APAG%'
                        THEN 'FALTA_ENERGIA'
                    WHEN UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%QUEIMA%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%DANO%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%EQUIPAMENTO%'
                        THEN 'DANO_EQUIPAMENTO'
                    WHEN UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%ARVORE%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%ÁRVORE%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%PODA%'
                        THEN 'VEGETACAO_REDE'
                    WHEN UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%POSTE%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%CABO%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%FIO%'
                      OR UPPER(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')) LIKE '%TRANSFORMADOR%'
                        THEN 'REDE_EQUIPAMENTO'
                    WHEN TEXTO_RECLAMACAO IS NULL AND TEXTO_RETORNO IS NULL
                        THEN 'SEM_TEXTO'
                    ELSE 'OUTROS'
                END AS TIPO_RECLAMACAO_PROVAVEL
            FROM reclamacoes
        ),
        {interrupcao_meta_cte}
        eventos_base AS (
            SELECT
                NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') AS UC,
                NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') AS NUM_OCORRENCIA_ADMS,
                NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') AS NUM_SEQ_INTRP,
                NULLIF(TRIM(CAST(NUM_INTRP_UCI AS VARCHAR)), '') AS NUM_INTRP_UCI,
                NULLIF(TRIM(CAST(NUM_POSTO_UCI AS VARCHAR)), '') AS NUM_POSTO_UCI,
                NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '') AS CONJUNTO,
                {apuracao_alim_expr} AS ALIM_INTRP_APURACAO,
                {apuracao_oper_chv_expr} AS NUM_OPER_CHV_INTRP_APURACAO,
                {apuracao_geo_chv_expr} AS NUM_GEO_CHV_INTRP_APURACAO,
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
        ),
        eventos AS (
            SELECT
                e.UC,
                e.NUM_OCORRENCIA_ADMS,
                e.NUM_SEQ_INTRP,
                e.NUM_INTRP_UCI,
                e.NUM_POSTO_UCI,
                e.CONJUNTO,
                COALESCE(e.ALIM_INTRP_APURACAO, m.ALIM_INTRP_META) AS ALIM_INTRP,
                COALESCE(e.NUM_OPER_CHV_INTRP_APURACAO, m.NUM_OPER_CHV_INTRP_META) AS NUM_OPER_CHV_INTRP,
                COALESCE(e.NUM_GEO_CHV_INTRP_APURACAO, m.NUM_GEO_CHV_INTRP_META) AS NUM_GEO_CHV_INTRP,
                e.TIPO_PROTOC_JUSTIF_UCI,
                e.COD_CAUSA_INTRP,
                e.COD_COMP_INTRP,
                e.INICIO_INTERRUPCAO_UC,
                e.FIM_INTERRUPCAO,
                e.DURACAO_HORA,
                e.CI_LIQUIDO,
                e.CHI_LIQUIDO
            FROM eventos_base e
            LEFT JOIN interrupcao_meta m
              ON m.NUM_OCORRENCIA_ADMS = e.NUM_OCORRENCIA_ADMS
             AND m.NUM_SEQ_INTRP = e.NUM_SEQ_INTRP
             AND m.NUM_INTRP_UCI = e.NUM_INTRP_UCI
        )
        SELECT
            r.ID_RECLAMACAO,
            r.UC,
            r.DTHR_RECLAMACAO,
            r.TEXTO_RECLAMACAO,
            r.TEXTO_RETORNO,
            r.TIPO_RECLAMACAO_PROVAVEL,
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
            END AS SCORE_VINCULO_RECLAMACAO,
            CASE
                WHEN e.NUM_SEQ_INTRP IS NULL AND r.TIPO_RECLAMACAO_PROVAVEL = 'FALTA_ENERGIA'
                    THEN 'FALTA_ENERGIA_SEM_OCORRENCIA_IQS'
                WHEN e.NUM_SEQ_INTRP IS NULL AND r.TIPO_RECLAMACAO_PROVAVEL = 'OSCILACAO_TENSAO'
                    THEN 'OSCILACAO_SEM_OCORRENCIA_IQS'
                WHEN e.NUM_SEQ_INTRP IS NULL
                    THEN 'SEM_OCORRENCIA_IQS'
                WHEN r.TIPO_RECLAMACAO_PROVAVEL = 'FALTA_ENERGIA'
                 AND r.DTHR_RECLAMACAO BETWEEN e.INICIO_INTERRUPCAO_UC AND e.FIM_INTERRUPCAO
                    THEN 'INTERRUPCAO_CONFIRMADA_DURANTE_RECLAMACAO'
                WHEN r.TIPO_RECLAMACAO_PROVAVEL = 'FALTA_ENERGIA'
                 AND r.DTHR_RECLAMACAO > e.FIM_INTERRUPCAO
                    THEN 'INTERRUPCAO_PROVAVEL_POS_RETORNO'
                WHEN r.TIPO_RECLAMACAO_PROVAVEL = 'OSCILACAO_TENSAO'
                    THEN 'OSCILACAO_TENSAO_ASSOCIADA_A_OCORRENCIA'
                WHEN r.TIPO_RECLAMACAO_PROVAVEL IN ('VEGETACAO_REDE', 'REDE_EQUIPAMENTO', 'DANO_EQUIPAMENTO')
                    THEN r.TIPO_RECLAMACAO_PROVAVEL || '_COM_OCORRENCIA_PROVAVEL'
                WHEN e.NUM_SEQ_INTRP IS NOT NULL
                    THEN 'OCORRENCIA_PROVAVEL_SEM_CAUSA_TEXTUAL_ESPECIFICA'
                ELSE 'INDEFINIDA'
            END AS CAUSA_PROVAVEL_RECLAMACAO
        FROM reclamacoes_classificadas r
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
            s.TEXTO_RECLAMACAO,
            s.TEXTO_RETORNO,
            s.TIPO_RECLAMACAO_PROVAVEL,
            s.CAUSA_PROVAVEL_RECLAMACAO,
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

    con.execute("ALTER TABLE gold_reclamacao_uc_vinculada ADD COLUMN DESC_CAUSA_INTRP VARCHAR")
    con.execute("ALTER TABLE gold_reclamacao_uc_vinculada ADD COLUMN DESC_COMP_INTRP VARCHAR")
    con.execute("ALTER TABLE gold_reclamacao_uc_vinculada ADD COLUMN GRUPO_CAUSA_IQS VARCHAR")
    con.execute("ALTER TABLE gold_reclamacao_uc_vinculada ADD COLUMN GRUPO_COMPONENTE_IQS VARCHAR")
    con.execute("ALTER TABLE gold_reclamacao_uc_vinculada ADD COLUMN ADERENCIA_RECLAMACAO_CAUSA_IQS VARCHAR")
    con.execute("ALTER TABLE gold_reclamacao_uc_vinculada ADD COLUMN PREVIA_CAUSA_RECLAMACAO VARCHAR")

    con.execute(
        """
        UPDATE gold_reclamacao_uc_vinculada g
        SET DESC_CAUSA_INTRP = r.DESC_CAUSA
        FROM ref_iqs_causa r
        WHERE TRIM(CAST(g.COD_CAUSA_INTRP AS VARCHAR)) = TRIM(CAST(r.COD_CAUSA AS VARCHAR))
        """
    )
    con.execute(
        """
        UPDATE gold_reclamacao_uc_vinculada g
        SET DESC_COMP_INTRP = r.DESC_COMP
        FROM ref_iqs_componente r
        WHERE TRIM(CAST(g.COD_COMP_INTRP AS VARCHAR)) = TRIM(CAST(r.COD_COMP AS VARCHAR))
        """
    )
    con.execute(
        """
        UPDATE gold_reclamacao_uc_vinculada
        SET
            GRUPO_CAUSA_IQS = CASE
                WHEN DESC_CAUSA_INTRP IS NULL THEN 'SEM_CAUSA_IQS'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%NAO IDENTIFICADA%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%NÃO IDENTIFICADA%'
                    THEN 'NAO_IDENTIFICADA'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%ARVORE%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%ÁRVORE%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%GALHO%'
                    THEN 'VEGETACAO'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%TENSAO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%TENSÃO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%DESEQUILIBRIO%'
                    THEN 'TENSAO_OSCILACAO'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%COMPONENTE%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%FALHA%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%DEFEITO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%MANUTENCAO CORRETIVA%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%CORROSAO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%OXIDACAO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%PONTO QUENTE%'
                    THEN 'FALHA_COMPONENTE'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%DESCARGA ATMOSFERICA%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%VENTO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%VENDAVAL%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%ANIMAIS%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%INSETOS%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%PASSAROS%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%PÁSSAROS%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%OBJETOS ESTRANHOS%'
                    THEN 'CLIMA_AMBIENTE'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%ABALROAMENTO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%TERCEIROS%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%VANDALISMO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%FURTO%'
                    THEN 'TERCEIROS'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%MANOBRA%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%TRANSF. CARGA%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%RETORNO CONFIG%'
                    THEN 'OPERACAO_REDE'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%QUEIMADA%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%INCENDIO%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%INCÊNDIO%'
                    THEN 'QUEIMADA_INCENDIO'
                WHEN UPPER(DESC_CAUSA_INTRP) LIKE '%INSP./MANUT.%'
                  OR UPPER(DESC_CAUSA_INTRP) LIKE '%EQUIPE DE EMERG%'
                    THEN 'INSPECAO_EMERGENCIA'
                ELSE 'OUTRA_CAUSA_IQS'
            END,
            GRUPO_COMPONENTE_IQS = CASE
                WHEN DESC_COMP_INTRP IS NULL THEN 'SEM_COMPONENTE_IQS'
                WHEN UPPER(DESC_COMP_INTRP) LIKE '%CHAVE%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%ELO FUSIVEL%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%FUSIVEL%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%ATUACAO DO RA%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%ATUAÇÃO DO RA%'
                    THEN 'CHAVE_PROTECAO'
                WHEN UPPER(DESC_COMP_INTRP) LIKE '%CONEC%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%GRAMPO%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%JUMPER%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%TERMINAIS%'
                    THEN 'CONEXAO'
                WHEN UPPER(DESC_COMP_INTRP) LIKE '%CONDUTOR%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%CABO%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%RAMAL%'
                    THEN 'CONDUTOR_RAMAL'
                WHEN UPPER(DESC_COMP_INTRP) LIKE '%REDE DE DISTRIBUICAO%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%REDE DE DISTRIBUIÇÃO%'
                    THEN 'REDE_DISTRIBUICAO'
                WHEN UPPER(DESC_COMP_INTRP) LIKE '%TRANSFORMADOR%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%TRAFO%'
                    THEN 'TRANSFORMADOR'
                WHEN UPPER(DESC_COMP_INTRP) LIKE '%POSTE%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%CRUZETA%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%ISOLADOR%'
                    THEN 'ESTRUTURA_REDE'
                WHEN UPPER(DESC_COMP_INTRP) LIKE '%MEDICAO%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%MEDIÇÃO%'
                  OR UPPER(DESC_COMP_INTRP) LIKE '%MEDIDOR%'
                    THEN 'MEDICAO'
                ELSE 'OUTRO_COMPONENTE_IQS'
            END
        """
    )
    con.execute(
        """
        UPDATE gold_reclamacao_uc_vinculada
        SET
            ADERENCIA_RECLAMACAO_CAUSA_IQS = CASE
                WHEN TEM_OCORRENCIA_PROVAVEL <> 'S' THEN 'SEM_OCORRENCIA_IQS'
                WHEN TIPO_RECLAMACAO_PROVAVEL = 'FALTA_ENERGIA'
                 AND GRUPO_CAUSA_IQS IN ('FALHA_COMPONENTE', 'VEGETACAO', 'TERCEIROS', 'OPERACAO_REDE', 'QUEIMADA_INCENDIO', 'CLIMA_AMBIENTE', 'INSPECAO_EMERGENCIA')
                    THEN 'ALTA'
                WHEN TIPO_RECLAMACAO_PROVAVEL = 'OSCILACAO_TENSAO'
                 AND GRUPO_CAUSA_IQS = 'TENSAO_OSCILACAO'
                    THEN 'ALTA'
                WHEN TIPO_RECLAMACAO_PROVAVEL = 'VEGETACAO_REDE'
                 AND GRUPO_CAUSA_IQS = 'VEGETACAO'
                    THEN 'ALTA'
                WHEN TIPO_RECLAMACAO_PROVAVEL IN ('REDE_EQUIPAMENTO', 'DANO_EQUIPAMENTO')
                 AND (
                    GRUPO_CAUSA_IQS = 'FALHA_COMPONENTE'
                    OR GRUPO_COMPONENTE_IQS IN ('CHAVE_PROTECAO', 'CONEXAO', 'CONDUTOR_RAMAL', 'REDE_DISTRIBUICAO', 'TRANSFORMADOR', 'ESTRUTURA_REDE')
                 )
                    THEN 'ALTA'
                WHEN TIPO_RECLAMACAO_PROVAVEL IN ('FALTA_ENERGIA', 'OSCILACAO_TENSAO', 'REDE_EQUIPAMENTO', 'DANO_EQUIPAMENTO', 'VEGETACAO_REDE')
                    THEN 'MEDIA'
                WHEN TIPO_RECLAMACAO_PROVAVEL = 'OUTROS' AND TEM_OCORRENCIA_PROVAVEL = 'S'
                    THEN 'BAIXA'
                ELSE 'INDEFINIDA'
            END,
            PREVIA_CAUSA_RECLAMACAO = CASE
                WHEN TEM_OCORRENCIA_PROVAVEL <> 'S'
                    THEN CAUSA_PROVAVEL_RECLAMACAO
                WHEN TIPO_RECLAMACAO_PROVAVEL = 'FALTA_ENERGIA'
                    THEN 'FALTA_ENERGIA | ' || COALESCE(GRUPO_CAUSA_IQS, 'SEM_CAUSA_IQS') || ' | ' || COALESCE(GRUPO_COMPONENTE_IQS, 'SEM_COMPONENTE_IQS')
                WHEN TIPO_RECLAMACAO_PROVAVEL = 'OSCILACAO_TENSAO'
                    THEN 'OSCILACAO_TENSAO | ' || COALESCE(GRUPO_CAUSA_IQS, 'SEM_CAUSA_IQS') || ' | ' || COALESCE(GRUPO_COMPONENTE_IQS, 'SEM_COMPONENTE_IQS')
                WHEN TIPO_RECLAMACAO_PROVAVEL IN ('REDE_EQUIPAMENTO', 'DANO_EQUIPAMENTO', 'VEGETACAO_REDE')
                    THEN TIPO_RECLAMACAO_PROVAVEL || ' | ' || COALESCE(GRUPO_CAUSA_IQS, 'SEM_CAUSA_IQS') || ' | ' || COALESCE(GRUPO_COMPONENTE_IQS, 'SEM_COMPONENTE_IQS')
                ELSE COALESCE(CAUSA_PROVAVEL_RECLAMACAO, 'OCORRENCIA_PROVAVEL_SEM_CAUSA_TEXTUAL_ESPECIFICA')
            END
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
            STRING_AGG(DISTINCT TIPO_RECLAMACAO_PROVAVEL, ', ' ORDER BY TIPO_RECLAMACAO_PROVAVEL) AS TIPOS_RECLAMACAO_PROVAVEIS,
            STRING_AGG(DISTINCT CAUSA_PROVAVEL_RECLAMACAO, ', ' ORDER BY CAUSA_PROVAVEL_RECLAMACAO) AS CAUSAS_PROVAVEIS_RECLAMACAO,
            STRING_AGG(DISTINCT PREVIA_CAUSA_RECLAMACAO, ', ' ORDER BY PREVIA_CAUSA_RECLAMACAO) AS PREVIAS_CAUSA_RECLAMACAO,
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
            MIN(DISTANCIA_MINUTOS) AS MENOR_DISTANCIA_MINUTOS,
            STRING_AGG(DISTINCT TIPO_RECLAMACAO_PROVAVEL, ', ' ORDER BY TIPO_RECLAMACAO_PROVAVEL) AS TIPOS_RECLAMACAO_PROVAVEIS,
            STRING_AGG(DISTINCT CAUSA_PROVAVEL_RECLAMACAO, ', ' ORDER BY CAUSA_PROVAVEL_RECLAMACAO) AS CAUSAS_PROVAVEIS_RECLAMACAO,
            STRING_AGG(DISTINCT PREVIA_CAUSA_RECLAMACAO, ', ' ORDER BY PREVIA_CAUSA_RECLAMACAO) AS PREVIAS_CAUSA_RECLAMACAO,
            STRING_AGG(DISTINCT GRUPO_CAUSA_IQS, ', ' ORDER BY GRUPO_CAUSA_IQS) AS GRUPOS_CAUSA_IQS,
            STRING_AGG(DISTINCT GRUPO_COMPONENTE_IQS, ', ' ORDER BY GRUPO_COMPONENTE_IQS) AS GRUPOS_COMPONENTE_IQS,
            SUM(CASE WHEN ADERENCIA_RECLAMACAO_CAUSA_IQS = 'ALTA' THEN 1 ELSE 0 END) AS QTD_ADERENCIA_ALTA,
            SUM(CASE WHEN ADERENCIA_RECLAMACAO_CAUSA_IQS = 'MEDIA' THEN 1 ELSE 0 END) AS QTD_ADERENCIA_MEDIA,
            SUM(CASE WHEN TIPO_RECLAMACAO_PROVAVEL = 'FALTA_ENERGIA' THEN 1 ELSE 0 END) AS QTD_RECLAMACOES_FALTA_ENERGIA,
            SUM(CASE WHEN TIPO_RECLAMACAO_PROVAVEL = 'OSCILACAO_TENSAO' THEN 1 ELSE 0 END) AS QTD_RECLAMACOES_OSCILACAO
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
        criar_referencias_iqs(con)
        criar_silver_reclamacoes(con)
        criar_gold_reclamacoes(con)
        exportar_resumo(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()

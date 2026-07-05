import os
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv

from midway.transform.iqs_raw_utils import materializar_gold_de_iqs_raw
from midway.apuracao.auditoria_sem_uc import (
    criar_gold_interrupcao_sem_uc,
    criar_gold_ocorrencia_sem_uc,
    exportar_auditoria_interrupcao_sem_uc,
)
from midway.apuracao.exportacoes import (
    exportar_bdo_interrupcao as _exportar_bdo_interrupcao,
    exportar_gold_continuidade_uc as _exportar_gold_continuidade_uc,
    exportar_gold_ressarcimento_prodist as _exportar_gold_ressarcimento_prodist,
)
from midway.apuracao.resumos import (
    anexar_compensacao_resumo_principal as _anexar_compensacao_resumo_principal,
    gerar_resumo as _gerar_resumo,
    obter_resumo_compensacao as _obter_resumo_compensacao,
)
from midway.apuracao.continuidade import criar_gold_continuidade_uc
from midway.apuracao.ressarcimento import criar_gold_ressarcimento_prodist
from midway.apuracao.conjunto import (
    criar_gold_impacto_conjunto_dia,
    criar_gold_meta_dia_critico_conjunto,
    exportar_gold_impacto_conjunto_dia as _exportar_gold_impacto_conjunto_dia,
    exportar_gold_meta_dia_critico_conjunto as _exportar_gold_meta_dia_critico_conjunto,
)
from midway.apuracao.duckdb_utils import normalizar_linhas_unix, sql_literal, tabela_local_existe


load_dotenv()

ANOMES = os.getenv("ANOMES", "202605")
TOTAL_CONSUMIDORES = os.getenv("TOTAL_CONSUMIDORES")

BASE_DIR = Path("data")
EXPORT_DIR = BASE_DIR / "export"
MARTS_DIR = BASE_DIR / "marts"
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
RAW_DUCKDB_PATH = BASE_DIR / "raw" / f"iqs_adms_raw_{ANOMES}.duckdb"

DATA_ARQ = datetime.now().strftime("%Y%m%d")
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")

def materializar_compatibilidade_gold(con, tabela_silver: str, tabela_gold: str):
    con.execute(
        f"""
        CREATE OR REPLACE TABLE {tabela_gold} AS
        SELECT *
        FROM {tabela_silver}
        """
    )

def validar_tabela_export(con):
    tabelas = {
        linha[0]
        for linha in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }

    if "adms_iqs_export" not in tabelas:
        raise RuntimeError(
            "Tabela adms_iqs_export nao encontrada. Execute run.bat tratamento "
            "ou run.bat exportar antes da apuracao previa."
        )


def total_consumidores_sql():
    if TOTAL_CONSUMIDORES is None or not str(TOTAL_CONSUMIDORES).strip():
        return "NULL"

    return str(TOTAL_CONSUMIDORES).replace(",", ".")


def tabela_gold_consumidores_existe(con):
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = 'gold_consumidores'
            """
        ).fetchone()[0]
        > 0
    )


def validar_gold_uc_fatura(con):
    existe = (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = 'gold_uc_fatura'
            """
        ).fetchone()[0]
        > 0
    )

    if not existe:
        raise RuntimeError(
            "Tabela gold_uc_fatura nao encontrada. Execute run.bat uc_fatura "
            "antes da apuracao."
        )


def _obsoleto_criar_gold_apuracao_uc_v1(con):
    if not tabela_local_existe(con, "silver_interrupcao_tratada"):
        if not tabela_local_existe(con, "gold_interrupcao_tratada"):
            raise RuntimeError("Tabela silver_interrupcao_tratada nao encontrada.")
        con.execute(
            """
            CREATE OR REPLACE TABLE silver_interrupcao_tratada AS
            SELECT *
            FROM gold_interrupcao_tratada
            """
        )

    con.execute("DROP TABLE IF EXISTS gold_apuracao_uc")
    con.execute("DROP TABLE IF EXISTS silver_interrupcao_uc_apuravel")
    con.execute(
        """
        CREATE TABLE silver_interrupcao_uc_apuravel AS
        WITH base AS (
            SELECT
                *,
                COALESCE(
                    TRY_STRPTIME(CAST(DATA_HORA_INIC_INTRP AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DATA_HORA_INIC_INTRP AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DATA_HORA_INIC_INTRP AS TIMESTAMP)
                ) AS DTHR_INICIO_INTRP_TS,
                COALESCE(
                    TRY_STRPTIME(CAST(DATA_HORA_FIM_INTRP AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DATA_HORA_FIM_INTRP AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)
                ) AS DTHR_FIM_INTRP_TS,
                COALESCE(
                    TRY_STRPTIME(CAST(DTHR_INICIO_INTRP_UC AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DTHR_INICIO_INTRP_UC AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                ) AS DTHR_INICIO_INTRP_UC_TS,
                CASE
                    WHEN NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NULL
                    THEN NULL
                    ELSE REGEXP_REPLACE(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '\\.0+$', '')
                END AS NUM_MOTIVO_TRAT_DIF_UCI_NORM,
                CASE
                    WHEN NULLIF(TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)), '') IS NULL
                    THEN NULL
                    ELSE UPPER(TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)))
                END AS INDIC_SIT_PROCES_INDIC_UCI_NORM
            FROM silver_interrupcao_tratada
        )
        SELECT
            CASE
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'P' THEN 'CSL'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'L' THEN 'NRT'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'M' THEN 'NRO'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'C' THEN 'LES'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'V' THEN 'OES'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) IN ('CSL', 'NRT', 'NRO', 'LES', 'OES')
                    THEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR))
                ELSE 'COPEL'
            END AS REGIONAL,
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            NUM_INTRP_UCI,
            NUM_POSTO_UCI,
            NUM_UC_UCI,
            ESTADO_INTRP,
            NUM_MOTIVO_TRAT_DIF_UCI,
            INDIC_SIT_PROCES_INDIC_UCI,
            TIPO_PROTOC_JUSTIF_UCI,
            CASE
                WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                THEN NULL
                ELSE NUM_INTRP_INIC_MANOBRA_UCI
            END AS NUM_INTRP_INIC_MANOBRA_UCI,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_TIPO_INTRP,
            DTHR_INICIO_INTRP_TS AS DATA_HORA_INIC_INTRP,
            DTHR_FIM_INTRP_TS AS DATA_HORA_FIM_INTRP,
            DTHR_INICIO_INTRP_UC_TS AS DTHR_INICIO_INTRP_UC,
            DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0 AS DURACAO_HORA,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                THEN 'SIM'
                ELSE 'NAO'
            END AS INTERRUPCAO_LONGA,
            CASE
                WHEN COALESCE(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IN ('', '0', '0.0')
                THEN 'SIM'
                ELSE 'NAO'
            END AS INTERRUPCAO_CONTABILIZAVEL,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND COALESCE(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IN ('', '0', '0.0')
                THEN 1
                ELSE 0
            END AS CI_BRUTO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND COALESCE(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IN ('', '0', '0.0')
                THEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0
                ELSE 0
            END AS CHI_BRUTO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND COALESCE(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IN ('', '0', '0.0')
                 AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                THEN 1
                ELSE 0
            END AS CI_LIQUIDO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND COALESCE(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IN ('', '0', '0.0')
                 AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                THEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0
                ELSE 0
            END AS CHI_LIQUIDO
        FROM base
        WHERE DTHR_INICIO_INTRP_UC_TS IS NOT NULL
          AND DTHR_FIM_INTRP_TS IS NOT NULL
          AND DTHR_FIM_INTRP_TS >= DTHR_INICIO_INTRP_UC_TS
          AND NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
          AND NUM_MOTIVO_TRAT_DIF_UCI IS NULL
          AND INDIC_SIT_PROCES_INDIC_UCI IS NULL
        """
    )


def criar_gold_apuracao_previa(con):
    usa_gold_consumidores = tabela_gold_consumidores_existe(con)
    total_sql = total_consumidores_sql()

    if usa_gold_consumidores:
        denominador_sql = """
            SELECT
                'COPEL' AS REGIONAL,
                UC_FATURADA AS TOTAL_CONSUMIDORES
            FROM gold_consumidores
            WHERE REGIONAL_TOTAL = 'COPEL'
        """
        total_consumidores_expr = "d.TOTAL_CONSUMIDORES"
        join_denominador = """
            CROSS JOIN denominador d
        """
    else:
        denominador_sql = f"""
            SELECT
                NULL AS REGIONAL,
                {total_sql} AS TOTAL_CONSUMIDORES
        """
        total_consumidores_expr = "d.TOTAL_CONSUMIDORES"
        join_denominador = """
            CROSS JOIN denominador d
        """

    con.execute("DROP TABLE IF EXISTS gold_apuracao_previa")
    con.execute(
        f"""
        CREATE TABLE gold_apuracao_previa AS
        WITH denominador AS (
            {denominador_sql}
        ),
        agg AS (
            SELECT
                REGIONAL,
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP,
                NUM_INTRP_UCI,
                NUM_POSTO_UCI,
                COD_CAUSA_INTRP,
                COD_COMP_INTRP,
                COD_TIPO_INTRP,
                STRFTIME(MIN(DATA_HORA_INIC_INTRP), '%d/%m/%Y %H:%M:%S') AS DATA_HORA_INIC_INTRP,
                STRFTIME(MAX(DATA_HORA_FIM_INTRP), '%d/%m/%Y %H:%M:%S') AS DATA_HORA_FIM_INTRP,
                COUNT(DISTINCT CASE
                    WHEN INTERRUPCAO_LONGA = 'SIM'
                     AND INTERRUPCAO_CONTABILIZAVEL = 'SIM'
                    THEN NUM_UC_UCI
                END) AS CI_BRUTO,
                SUM(CASE
                    WHEN INTERRUPCAO_LONGA = 'SIM'
                     AND INTERRUPCAO_CONTABILIZAVEL = 'SIM'
                    THEN DURACAO_HORA
                    ELSE 0
                END) AS CHI_BRUTO,
                COUNT(DISTINCT CASE
                    WHEN INTERRUPCAO_LONGA = 'SIM'
                     AND INTERRUPCAO_CONTABILIZAVEL = 'SIM'
                     AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                    THEN NUM_UC_UCI
                END) AS CI_LIQUIDO,
                SUM(CASE
                    WHEN INTERRUPCAO_LONGA = 'SIM'
                     AND INTERRUPCAO_CONTABILIZAVEL = 'SIM'
                     AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                    THEN DURACAO_HORA
                    ELSE 0
                END) AS CHI_LIQUIDO
            FROM gold_apuracao_uc
            WHERE INTERRUPCAO_LONGA = 'SIM'
              AND INTERRUPCAO_CONTABILIZAVEL = 'SIM'
            GROUP BY
                REGIONAL,
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP,
                NUM_INTRP_UCI,
                NUM_POSTO_UCI,
                COD_CAUSA_INTRP,
                COD_COMP_INTRP,
                COD_TIPO_INTRP
        )
        SELECT
            agg.REGIONAL,
            agg.NUM_OCORRENCIA_ADMS,
            agg.NUM_SEQ_INTRP,
            agg.NUM_INTRP_UCI,
            agg.NUM_POSTO_UCI,
            agg.COD_CAUSA_INTRP,
            agg.COD_COMP_INTRP,
            agg.COD_TIPO_INTRP,
            agg.DATA_HORA_INIC_INTRP,
            agg.DATA_HORA_FIM_INTRP,
            agg.CI_BRUTO,
            agg.CHI_BRUTO,
            agg.CI_LIQUIDO,
            agg.CHI_LIQUIDO,
            {total_consumidores_expr} AS TOTAL_CONSUMIDORES,
            CASE
                WHEN {total_consumidores_expr} IS NULL OR {total_consumidores_expr} = 0 THEN NULL
                ELSE agg.CHI_BRUTO / {total_consumidores_expr}
            END AS DEC_BRUTO,
            CASE
                WHEN {total_consumidores_expr} IS NULL OR {total_consumidores_expr} = 0 THEN NULL
                ELSE agg.CI_BRUTO / {total_consumidores_expr}
            END AS FEC_BRUTO,
            CASE
                WHEN {total_consumidores_expr} IS NULL OR {total_consumidores_expr} = 0 THEN NULL
                ELSE agg.CHI_LIQUIDO / {total_consumidores_expr}
            END AS DEC_LIQUIDO,
            CASE
                WHEN {total_consumidores_expr} IS NULL OR {total_consumidores_expr} = 0 THEN NULL
                ELSE agg.CI_LIQUIDO / {total_consumidores_expr}
            END AS FEC_LIQUIDO
        FROM agg
        {join_denominador}
        """
    )






def _obsoleto_apuracao_previa_v1():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    con.execute("SET preserve_insertion_order=false")

    validar_tabela_export(con)

    print("Criando gold_interrupcao_tratada...")
    criar_gold_interrupcao_tratada(con)

    print("Criando gold_apuracao_uc...")
    criar_gold_apuracao_uc(con)

    print("Criando gold_apuracao_previa...")
    criar_gold_apuracao_previa(con)

    print("Exportando BDO_interupcao...")
    caminho_csv = exportar_bdo_interrupcao(con)
    caminho_resumo = gerar_resumo(con, caminho_csv)

    con.close()

    print(f"BDO exportado: {caminho_csv}")
    print(f"Resumo exportado: {caminho_resumo}")
    print("Apuracao previa concluida.")


def _obsoleto_criar_gold_apuracao_uc_v2(con):
    if not tabela_local_existe(con, "silver_interrupcao_tratada"):
        if not tabela_local_existe(con, "gold_interrupcao_tratada"):
            raise RuntimeError("Tabela silver_interrupcao_tratada nao encontrada.")
        con.execute(
            """
            CREATE OR REPLACE TABLE silver_interrupcao_tratada AS
            SELECT *
            FROM gold_interrupcao_tratada
            """
        )

    con.execute("DROP TABLE IF EXISTS gold_apuracao_uc")
    con.execute("DROP TABLE IF EXISTS silver_interrupcao_uc_apuravel")
    con.execute(
        """
        CREATE TABLE silver_interrupcao_uc_apuravel AS
        WITH base AS (
            SELECT
                *,
                COALESCE(
                    TRY_STRPTIME(CAST(DATA_HORA_INIC_INTRP AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DATA_HORA_INIC_INTRP AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DATA_HORA_INIC_INTRP AS TIMESTAMP)
                ) AS DTHR_INICIO_INTRP_TS,
                COALESCE(
                    TRY_STRPTIME(CAST(DATA_HORA_FIM_INTRP AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DATA_HORA_FIM_INTRP AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)
                ) AS DTHR_FIM_INTRP_TS,
                COALESCE(
                    TRY_STRPTIME(CAST(DTHR_INICIO_INTRP_UC AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DTHR_INICIO_INTRP_UC AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                ) AS DTHR_INICIO_INTRP_UC_TS,
                CASE
                    WHEN NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NULL
                    THEN NULL
                    ELSE REGEXP_REPLACE(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '\\.0+$', '')
                END AS NUM_MOTIVO_TRAT_DIF_UCI_NORM,
                CASE
                    WHEN NULLIF(TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)), '') IS NULL
                    THEN NULL
                    ELSE UPPER(TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)))
                END AS INDIC_SIT_PROCES_INDIC_UCI_NORM
            FROM silver_interrupcao_tratada
        )
        SELECT
            CASE
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'P' THEN 'CSL'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'L' THEN 'NRT'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'M' THEN 'NRO'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'C' THEN 'LES'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'V' THEN 'OES'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) IN ('CSL', 'NRT', 'NRO', 'LES', 'OES')
                    THEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR))
                ELSE 'COPEL'
            END AS REGIONAL,
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            NUM_INTRP_UCI,
            NUM_POSTO_UCI,
            NUM_UC_UCI,
            ESTADO_INTRP,
            NUM_MOTIVO_TRAT_DIF_UCI,
            INDIC_SIT_PROCES_INDIC_UCI,
            TIPO_PROTOC_JUSTIF_UCI,
            NUM_INTRP_INIC_MANOBRA_UCI,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_TIPO_INTRP,
            DTHR_INICIO_INTRP_TS AS DATA_HORA_INIC_INTRP,
            DTHR_FIM_INTRP_TS AS DATA_HORA_FIM_INTRP,
            DTHR_INICIO_INTRP_UC_TS AS DTHR_INICIO_INTRP_UC,
            DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0 AS DURACAO_HORA,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                THEN 'SIM'
                ELSE 'NAO'
            END AS INTERRUPCAO_LONGA,
            CASE
                WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                THEN 'SIM'
                ELSE 'NAO'
            END AS INTERRUPCAO_CONTABILIZAVEL,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                THEN 1
                ELSE 0
            END AS CI_BRUTO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                THEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0
                ELSE 0
            END AS CHI_BRUTO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                 AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                THEN 1
                ELSE 0
            END AS CI_LIQUIDO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                 AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                THEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0
                ELSE 0
            END AS CHI_LIQUIDO
        FROM base
        WHERE DTHR_INICIO_INTRP_UC_TS IS NOT NULL
          AND DTHR_FIM_INTRP_TS IS NOT NULL
          AND DTHR_FIM_INTRP_TS >= DTHR_INICIO_INTRP_UC_TS
          AND NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NULL
        """
    )


def criar_gold_apuracao_uc_base(con):
    if not tabela_local_existe(con, "silver_interrupcao_tratada"):
        if not tabela_local_existe(con, "gold_interrupcao_tratada"):
            raise RuntimeError("Tabela silver_interrupcao_tratada nao encontrada.")
        con.execute(
            """
            CREATE OR REPLACE TABLE silver_interrupcao_tratada AS
            SELECT *
            FROM gold_interrupcao_tratada
            """
        )

    con.execute("DROP TABLE IF EXISTS gold_apuracao_uc")
    con.execute("DROP TABLE IF EXISTS silver_interrupcao_uc_apuravel")
    con.execute(
        """
        CREATE TABLE silver_interrupcao_uc_apuravel AS
        WITH base AS (
            SELECT
                *,
                CASE
                    WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NULL
                    THEN NULL
                    WHEN TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) IN ('0', '0.0')
                    THEN NULL
                    WHEN TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) = TRIM(CAST(NUM_INTRP_UCI AS VARCHAR))
                    THEN NULL
                    WHEN TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) = TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                    THEN NULL
                    ELSE CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)
                END AS NUM_INTRP_INIC_MANOBRA_UCI_NORM,
                COALESCE(
                    TRY_STRPTIME(CAST(DATA_HORA_INIC_INTRP AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DATA_HORA_INIC_INTRP AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DATA_HORA_INIC_INTRP AS TIMESTAMP)
                ) AS DTHR_INICIO_INTRP_TS,
                COALESCE(
                    TRY_STRPTIME(CAST(DATA_HORA_FIM_INTRP AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DATA_HORA_FIM_INTRP AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)
                ) AS DTHR_FIM_INTRP_TS,
                COALESCE(
                    TRY_STRPTIME(CAST(DTHR_INICIO_INTRP_UC AS VARCHAR), '%d/%m/%Y %H:%M:%S'),
                    TRY_STRPTIME(CAST(DTHR_INICIO_INTRP_UC AS VARCHAR), '%Y-%m-%d %H:%M:%S'),
                    TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                ) AS DTHR_INICIO_INTRP_UC_TS,
                CASE
                    WHEN NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NULL
                    THEN NULL
                    ELSE REGEXP_REPLACE(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '\\.0+$', '')
                END AS NUM_MOTIVO_TRAT_DIF_UCI_NORM,
                CASE
                    WHEN NULLIF(TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)), '') IS NULL
                    THEN NULL
                    ELSE UPPER(TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)))
                END AS INDIC_SIT_PROCES_INDIC_UCI_NORM
            FROM silver_interrupcao_tratada
        )
        SELECT
            CASE
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'P' THEN 'CSL'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'L' THEN 'NRT'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'M' THEN 'NRO'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'C' THEN 'LES'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) = 'V' THEN 'OES'
                WHEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)) IN ('CSL', 'NRT', 'NRO', 'LES', 'OES')
                    THEN TRIM(CAST(SIGLA_REGIONAL AS VARCHAR))
                ELSE 'COPEL'
            END AS REGIONAL,
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            NUM_INTRP_UCI,
            NUM_POSTO_UCI,
            NUM_UC_UCI,
            ESTADO_INTRP,
            NUM_MOTIVO_TRAT_DIF_UCI_NORM AS NUM_MOTIVO_TRAT_DIF_UCI,
            INDIC_SIT_PROCES_INDIC_UCI_NORM AS INDIC_SIT_PROCES_INDIC_UCI,
            TIPO_PROTOC_JUSTIF_UCI,
            NUM_INTRP_INIC_MANOBRA_UCI_NORM AS NUM_INTRP_INIC_MANOBRA_UCI,
            COD_CONJTO_ELET_ANEEL_INTRP,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_TIPO_INTRP,
            DTHR_INICIO_INTRP_TS AS DATA_HORA_INIC_INTRP,
            DTHR_FIM_INTRP_TS AS DATA_HORA_FIM_INTRP,
            DTHR_INICIO_INTRP_UC_TS AS DTHR_INICIO_INTRP_UC,
            DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0 AS DURACAO_HORA,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                THEN 'SIM'
                ELSE 'NAO'
            END AS INTERRUPCAO_LONGA,
            CASE
                WHEN NUM_INTRP_INIC_MANOBRA_UCI_NORM IS NULL
                THEN 'SIM'
                ELSE 'NAO'
            END AS INTERRUPCAO_CONTABILIZAVEL,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND NUM_INTRP_INIC_MANOBRA_UCI_NORM IS NULL
                THEN 1
                ELSE 0
            END AS CI_BRUTO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND NUM_INTRP_INIC_MANOBRA_UCI_NORM IS NULL
                THEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0
                ELSE 0
            END AS CHI_BRUTO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND NUM_INTRP_INIC_MANOBRA_UCI_NORM IS NULL
                 AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                THEN 1
                ELSE 0
            END AS CI_LIQUIDO,
            CASE
                WHEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) >= 180
                 AND NUM_INTRP_INIC_MANOBRA_UCI_NORM IS NULL
                 AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                THEN DATE_DIFF('second', DTHR_INICIO_INTRP_UC_TS, DTHR_FIM_INTRP_TS) / 3600.0
                ELSE 0
            END AS CHI_LIQUIDO
        FROM base
        WHERE DTHR_INICIO_INTRP_UC_TS IS NOT NULL
          AND DTHR_FIM_INTRP_TS IS NOT NULL
          AND DTHR_FIM_INTRP_TS >= DTHR_INICIO_INTRP_UC_TS
          AND NUM_INTRP_INIC_MANOBRA_UCI_NORM IS NULL
          AND EXISTS (
              SELECT 1
              FROM gold_uc_fatura u
              WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(base.NUM_UC_UCI AS VARCHAR))
                AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
           )
           AND NUM_MOTIVO_TRAT_DIF_UCI_NORM IS NULL
        """
    )
    materializar_compatibilidade_gold(
        con, "silver_interrupcao_uc_apuravel", "gold_apuracao_uc"
    )


def anexar_raw(con):
    if not RAW_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB bruto nao encontrado: {RAW_DUCKDB_PATH}")

    con.execute(f"ATTACH {sql_literal(RAW_DUCKDB_PATH.as_posix())} AS raw_db (READ_ONLY)")


def criar_gold_interrupcao_tratada(con):
    con.execute("DROP TABLE IF EXISTS gold_interrupcao_tratada")
    con.execute(
        """
        CREATE TABLE gold_interrupcao_tratada AS
        WITH raw_base AS (
            SELECT
                CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS PID_INTRP_CONJTO_PIN,
                CAST(r.PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR) AS PID_POSTO_PIN,
                CAST(r.INDIC_AREA_REDE_POSTO_PIN_PRIM_HIADMS AS VARCHAR) AS INDIC_AREA_REDE_POSTO_PIN,
                CAST(r.NUM_ALIM_INTRP_PIN_PRIM_HIADMS AS VARCHAR) AS ALIM_INTRP_PIN,
                CAST(r.ESTADO_INTRP_ULT_HIADMS AS VARCHAR) AS ESTADO_INTRP_RAW,
                CAST(r.ALIM_INTRP_PRIM_HIADMS AS VARCHAR) AS ALIM_INTRP,
                CAST(r.CAR_SE_INTRP_PRIM_HIADMS AS VARCHAR) AS CAR_SE,
                CAST(r.INDIC_INTRP_SE_ALIM_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_INTRP_SE_ALIM,
                CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                CAST(r.INDIC_INTRP_AT_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_INTRP_AT,
                CAST(r.CONS_INTRP_PRIM_HIADMS AS VARCHAR) AS CONS_INTRP,
                CAST(r.KVA_INTRP_PRIM_HIADMS AS VARCHAR) AS KVA_INTRP,
                CAST(r.NUM_OPER_CHV_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OPER_CHV_INTRP,
                CAST(r.NUM_FUNCAO_ELET_INTRP_PRIM_HIADMS AS VARCHAR) AS NUM_FUNCAO_ELET_HCAI,
                CAST(r.NUM_FUNCAO_ELET_INTRP_PRIM_HIADMS AS VARCHAR) AS DESC_INTRP,
                CAST(r.INDIC_VALID_POS_OPER_INTRP_ULT_HIADMS AS VARCHAR) AS VALID_POS_OPERACAO,
                r.DATA_HORA_INIC_INTRP_ULT_HIADMS AS DATA_HORA_INIC_INTRP,
                r.DATA_HORA_FIM_INTRP_ULT_HIADMS AS DATA_HORA_FIM_INTRP,
                CAST(r.TIPO_EQP_INTRP_PRIM_HIADMS AS VARCHAR) AS TIPO_EQP_INTRP,
                CAST(r.COORD_X_INTRP_PRIM_HIADMS AS VARCHAR) AS COORD_X_INTRP,
                CAST(r.COORD_Y_INTRP_PRIM_HIADMS AS VARCHAR) AS COORD_Y_INTRP,
                CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(r.COD_CAUSA_INTRP_ULT_HIADMS AS VARCHAR) AS COD_CAUSA_INTRP,
                CAST(r.COD_COMP_INTRP_ULT_HIADMS AS VARCHAR) AS COD_COMP_INTRP,
                CAST(r.COD_AREA_ELET_INTRP_ULT_HIADMS AS VARCHAR) AS COD_AREA_ELET_INTRP,
                CAST(r.COD_GRUPO_COMP_INTRP_ULT_HIADMS AS VARCHAR) AS COD_GRUPO_COMP_INTRP,
                CAST(r.COD_COND_CLIMA_INTRP_ULT_HIADMS AS VARCHAR) AS COD_COND_CLIMA_INTRP,
                CAST(r.COD_TIPO_INTRP_ULT_HIADMS AS VARCHAR) AS COD_TIPO_INTRP,
                CAST(r.INDIC_JUMP_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_JUMP_INTRP,
                CAST(r.NUM_PROTOC_JUSTIF_RESP_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_PROTOC_JUSTIF_RESP_INTRP,
                CAST(r.TIPO_PROTOC_JUSTIF_INTRP_ULT_HIADMS AS VARCHAR) AS TIPO_PROTOC_JUSTIF_INTRP,
                CAST(r.COD_CONJTO_ELET_ANEEL_INTRP_PRIM_HIADMS AS VARCHAR) AS COD_CONJTO_ELET_ANEEL_INTRP,
                CAST(r.INDIC_CALC_DMIC_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_CALC_DMIC_INTRP,
                CAST(r.INDIC_PONTO_CONEX_INTRP_PRIM_HIADMS AS VARCHAR) AS INDIC_PONTO_CONEX_INTRP,
                CAST(r.NUM_GEO_CHV_INTRP_PRIM_HIADMS AS VARCHAR) AS NUM_GEO_CHV_INTRP,
                CAST(r.TIPO_REDE_CHV_INTRP_PRIM_HIADMS AS VARCHAR) AS TIPO_REDE_CHV_INTRP,
                CAST(r.TIPO_CHV_INTRP_PRIM_HIADMS AS VARCHAR) AS TIPO_CHV_INTRP,
                CAST(r.INDIC_PROPR_POSTO_INTRP_PRIM_HIADMS AS VARCHAR) AS INDIC_PROPR_POSTO_INTRP,
                CAST(r.TENSAO_OPER_ALIM_INTRP_PRIM_HIADMS AS VARCHAR) AS TENSAO_OPER_ALIM_INTRP,
                CAST(r.INDIC_DESLIG_ENT_SERV_INTRP_ULT_HIADMS AS VARCHAR) AS INDIC_DESLIG_ENT_SERV_INTRP,
                CAST(r.INDIC_PROPR_CHVP_INTRP_PRIM_HIADMS AS VARCHAR) AS INDIC_PROPR_CHVP_INTRP,
                CAST(r.INDIC_CHVP_INIC_ALIM_INTRP_PRIM_HIADMS AS VARCHAR) AS INDIC_CHVP_INIC_ALIM_INTRP,
                CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS PID,
                CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS PID_INTRP_UCI,
                CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_INTRP_UCI,
                CAST(r.PID_POSTO_PIN_PRIM_HIADMS AS VARCHAR) AS NUM_POSTO_UCI,
                CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS NUM_UC_UCI,
                CAST(r.TIPO_SIT_UC_UCI_PRIM_HIADMS AS VARCHAR) AS TIPO_SIT_UC_UCI,
                r.DATA_HORA_INIC_INTRP_ULT_HIADMS AS DTHR_INICIO_INTRP_UC_RAW,
                CAST(r.NUM_INTRP_INIC_MANOBRA_UCI_ULT_HIADMS AS VARCHAR) AS NUM_INTRP_INIC_MANOBRA_UCI_RAW,
                CAST(r.NUM_MOTIVO_TRAT_DIF_UCI_ULT_HIADMS AS VARCHAR) AS NUM_MOTIVO_TRAT_DIF_UCI_RAW,
                CAST(r.INDIC_UC_ACESS_UCI_PRIM_HIADMS AS VARCHAR) AS UC_ACESSANTE,
                CAST(r.SIGLA_REGIONAL_INTRP_PRIM_HIADMS AS VARCHAR) AS SIGLA_REGIONAL,
                CAST(r.NUM_PROTOC_JUSTIF_RESP_UCI_ULT_HIADMS AS VARCHAR) AS NUM_PROTOC_JUSTIF_RESP_UCI,
                CAST(r.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR) AS TIPO_PROTOC_JUSTIF_UCI,
                CAST(r.PID_PIN_PRIM_HIADMS AS VARCHAR) AS PID_PIN,
                CAST(r.INDIC_PROCES_IND_PIN_ULT_HIADMS AS VARCHAR) AS INDIC_PROCES_IND_PIN,
                CAST(r.INDIC_SIT_PROCES_INDIC_UCI_ULT_HIADMS AS VARCHAR) AS INDIC_SIT_PROCES_INDIC_UCI_RAW
            FROM raw_db.hiadms_raw r
            WHERE r.DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
              AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
              AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS >= r.DATA_HORA_INIC_INTRP_ULT_HIADMS
              AND NULLIF(TRIM(CAST(r.COD_CAUSA_INTRP_ULT_HIADMS AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(r.COD_COMP_INTRP_ULT_HIADMS AS VARCHAR)), '') IS NOT NULL
        ),
        tratado AS (
            SELECT
                b.*,
                t.ESTADO_INTRP AS ESTADO_INTRP_TRAT,
                t.NUM_MOTIVO_TRAT_DIF_UCI AS NUM_MOTIVO_TRAT_DIF_UCI_TRAT,
                t.INDIC_SIT_PROCES_INDIC_UCI AS INDIC_SIT_PROCES_INDIC_UCI_TRAT,
                t.DTHR_INICIO_INTRP_UC AS DTHR_INICIO_INTRP_UC_TRAT,
                t.NUM_INTRP_INIC_MANOBRA_UCI AS NUM_INTRP_INIC_MANOBRA_UCI_TRAT,
                t.ACAO_AJUSTE_PARCIAL,
                t.ACAO_REDIREC_MANOBRA_ESTADO_7
            FROM raw_base b
            LEFT JOIN adms_iqs_alterados t
              ON COALESCE(TRIM(CAST(t.NUM_OCORRENCIA_ADMS AS VARCHAR)), '') = COALESCE(TRIM(CAST(b.NUM_OCORRENCIA_ADMS AS VARCHAR)), '')
             AND COALESCE(TRIM(CAST(t.NUM_SEQ_INTRP AS VARCHAR)), '') = COALESCE(TRIM(CAST(b.NUM_SEQ_INTRP AS VARCHAR)), '')
             AND COALESCE(TRIM(CAST(t.NUM_UC_UCI AS VARCHAR)), '') = COALESCE(TRIM(CAST(b.NUM_UC_UCI AS VARCHAR)), '')
             AND COALESCE(TRIM(CAST(t.NUM_POSTO_UCI AS VARCHAR)), '') = COALESCE(TRIM(CAST(b.NUM_POSTO_UCI AS VARCHAR)), '')
        )
        SELECT DISTINCT
            PID_INTRP_CONJTO_PIN,
            PID_POSTO_PIN,
            INDIC_AREA_REDE_POSTO_PIN,
            ALIM_INTRP_PIN,
            COALESCE(ESTADO_INTRP_TRAT, ESTADO_INTRP_RAW) AS ESTADO_INTRP,
            ALIM_INTRP,
            CAR_SE,
            INDIC_INTRP_SE_ALIM,
            NUM_OCORRENCIA_ADMS,
            INDIC_INTRP_AT,
            CONS_INTRP,
            KVA_INTRP,
            NUM_OPER_CHV_INTRP,
            NUM_FUNCAO_ELET_HCAI,
            DESC_INTRP,
            VALID_POS_OPERACAO,
            DATA_HORA_INIC_INTRP,
            DATA_HORA_FIM_INTRP,
            TIPO_EQP_INTRP,
            COORD_X_INTRP,
            COORD_Y_INTRP,
            NUM_SEQ_INTRP,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_AREA_ELET_INTRP,
            COD_GRUPO_COMP_INTRP,
            COD_COND_CLIMA_INTRP,
            COD_TIPO_INTRP,
            INDIC_JUMP_INTRP,
            NUM_PROTOC_JUSTIF_RESP_INTRP,
            TIPO_PROTOC_JUSTIF_INTRP,
            COD_CONJTO_ELET_ANEEL_INTRP,
            INDIC_CALC_DMIC_INTRP,
            INDIC_PONTO_CONEX_INTRP,
            NUM_GEO_CHV_INTRP,
            TIPO_REDE_CHV_INTRP,
            TIPO_CHV_INTRP,
            INDIC_PROPR_POSTO_INTRP,
            TENSAO_OPER_ALIM_INTRP,
            INDIC_DESLIG_ENT_SERV_INTRP,
            INDIC_PROPR_CHVP_INTRP,
            INDIC_CHVP_INIC_ALIM_INTRP,
            PID,
            PID_INTRP_UCI,
            NUM_INTRP_UCI,
            NUM_POSTO_UCI,
            NUM_UC_UCI,
            TIPO_SIT_UC_UCI,
            CASE
                WHEN ACAO_AJUSTE_PARCIAL IS NOT NULL THEN DTHR_INICIO_INTRP_UC_TRAT
                ELSE DTHR_INICIO_INTRP_UC_RAW
            END AS DTHR_INICIO_INTRP_UC,
            CASE
                WHEN ACAO_AJUSTE_PARCIAL IS NOT NULL
                  OR ACAO_REDIREC_MANOBRA_ESTADO_7 IS NOT NULL
                THEN NUM_INTRP_INIC_MANOBRA_UCI_TRAT
                ELSE NUM_INTRP_INIC_MANOBRA_UCI_RAW
            END AS NUM_INTRP_INIC_MANOBRA_UCI,
            COALESCE(NUM_MOTIVO_TRAT_DIF_UCI_TRAT, NUM_MOTIVO_TRAT_DIF_UCI_RAW) AS NUM_MOTIVO_TRAT_DIF_UCI,
            UC_ACESSANTE,
            SIGLA_REGIONAL,
            NUM_PROTOC_JUSTIF_RESP_UCI,
            TIPO_PROTOC_JUSTIF_UCI,
            PID_PIN,
            INDIC_PROCES_IND_PIN,
            COALESCE(INDIC_SIT_PROCES_INDIC_UCI_TRAT, INDIC_SIT_PROCES_INDIC_UCI_RAW) AS INDIC_SIT_PROCES_INDIC_UCI
        FROM tratado
        WHERE TRIM(CAST(COALESCE(ESTADO_INTRP_TRAT, ESTADO_INTRP_RAW) AS VARCHAR)) = '4'
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE silver_interrupcao_tratada AS
        SELECT *
        FROM gold_interrupcao_tratada
        """
    )




def exportar_bdo_interrupcao(con):
    return _exportar_bdo_interrupcao(
        con,
        export_dir=EXPORT_DIR,
        data_arq=DATA_ARQ,
        timestamp=TIMESTAMP_ARQ,
    )


def gerar_resumo(con, caminho_csv):
    return _gerar_resumo(
        con,
        caminho_csv,
        marts_dir=MARTS_DIR,
        timestamp=TIMESTAMP_ARQ,
        anomes=ANOMES,
        processed_duckdb_path=PROCESSED_DUCKDB_PATH,
        tabela_gold_consumidores_existe=tabela_gold_consumidores_existe,
    )


def exportar_gold_ressarcimento_prodist(con):
    return _exportar_gold_ressarcimento_prodist(
        con,
        marts_dir=MARTS_DIR,
        anomes=ANOMES,
        timestamp=TIMESTAMP_ARQ,
    )


def exportar_gold_continuidade_uc(con):
    return _exportar_gold_continuidade_uc(
        con,
        marts_dir=MARTS_DIR,
        anomes=ANOMES,
        timestamp=TIMESTAMP_ARQ,
    )


def obter_resumo_compensacao(con):
    return _obter_resumo_compensacao(con)


def anexar_compensacao_resumo_principal(con):
    return _anexar_compensacao_resumo_principal(
        con,
        export_dir=EXPORT_DIR,
        anomes=ANOMES,
        obter_resumo_compensacao=obter_resumo_compensacao,
    )

def apuracao_previa():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    con.execute("SET preserve_insertion_order=false")
    anexar_raw(con)
    tabelas_iqs = materializar_gold_de_iqs_raw(con, ANOMES)
    if tabelas_iqs:
        print("Tabelas IQS sincronizadas do raw: " + ", ".join(tabelas_iqs))
    validar_gold_uc_fatura(con)

    print("Criando gold_interrupcao_tratada completa do RAW...")
    criar_gold_interrupcao_tratada(con)

    print("Criando gold_apuracao_uc...")
    criar_gold_apuracao_uc(con)

    print("Criando gold_apuracao_previa...")
    criar_gold_apuracao_previa(con)

    print("Exportando BDO_interupcao...")
    caminho_csv = exportar_bdo_interrupcao(con)
    caminho_resumo = gerar_resumo(con, caminho_csv)

    con.close()

    print(f"BDO exportado: {caminho_csv}")
    print(f"Resumo exportado: {caminho_resumo}")
    print("Apuracao previa concluida.")






def exportar_gold_impacto_conjunto_dia(con):
    return _exportar_gold_impacto_conjunto_dia(
        con,
        marts_dir=MARTS_DIR,
        anomes=ANOMES,
        timestamp=TIMESTAMP_ARQ,
        processed_duckdb_path=PROCESSED_DUCKDB_PATH,
    )


def exportar_gold_meta_dia_critico_conjunto(con):
    return _exportar_gold_meta_dia_critico_conjunto(
        con,
        marts_dir=MARTS_DIR,
        anomes=ANOMES,
        timestamp=TIMESTAMP_ARQ,
        processed_duckdb_path=PROCESSED_DUCKDB_PATH,
    )










_criar_gold_apuracao_uc_original = criar_gold_apuracao_uc_base


def criar_gold_apuracao_uc(con):
    if not globals().get("_AUDITORIA_INTERRUPCAO_SEM_UC_EXECUTADA", False):
        criar_gold_interrupcao_sem_uc(con)
        criar_gold_ocorrencia_sem_uc(con)
        exportar_auditoria_interrupcao_sem_uc(
            con,
            marts_dir=MARTS_DIR,
            anomes=ANOMES,
            timestamp=TIMESTAMP_ARQ,
        )
        globals()["_AUDITORIA_INTERRUPCAO_SEM_UC_EXECUTADA"] = True

    resultado = _criar_gold_apuracao_uc_original(con)
    criar_gold_continuidade_uc(con)
    criar_gold_ressarcimento_prodist(con)
    criar_gold_impacto_conjunto_dia(con)
    criar_gold_meta_dia_critico_conjunto(con)
    exportar_gold_continuidade_uc(con)
    exportar_gold_ressarcimento_prodist(con)
    exportar_gold_impacto_conjunto_dia(con)
    exportar_gold_meta_dia_critico_conjunto(con)
    anexar_compensacao_resumo_principal(con)
    return resultado


if __name__ == "__main__":
    apuracao_previa()

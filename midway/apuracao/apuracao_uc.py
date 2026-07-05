from midway.apuracao.duckdb_utils import tabela_local_existe


def criar_gold_apuracao_uc_base(
    con,
    *,
    materializar_compatibilidade_gold,
):
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

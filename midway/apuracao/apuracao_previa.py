def criar_gold_apuracao_previa(
    con,
    *,
    total_consumidores_sql,
    tabela_gold_consumidores_existe,
):
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

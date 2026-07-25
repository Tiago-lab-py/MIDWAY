import duckdb
from pathlib import Path

def run():
    anomes = "202607"
    db_path = Path("data/processed") / f"iqs_adms_processed_{anomes}.duckdb"
    
    print(f"Connecting to {db_path}...")
    with duckdb.connect(str(db_path), read_only=True) as con:
        print("Executing second query...")
        try:
            tratamentos = con.execute(
                """
                WITH denominador AS (
                    SELECT MAX(UC_FATURADA) AS total_consumidores
                    FROM gold_consumidores
                    WHERE REGIONAL_TOTAL = 'COPEL'
                ),
                impacto_total AS (
                    SELECT
                        'Sobreposição total UC' AS tratamento,
                        COUNT(*) AS ci_bruto_ganho,
                        SUM(DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0) AS chi_bruto_ganho,
                        SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido_ganho,
                        SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                            THEN DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0 ELSE 0 END) AS chi_liquido_ganho
                    FROM export_sobreposicao_total_uc e
                    WHERE TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                      AND DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) >= 180
                      AND EXISTS (
                          SELECT 1 FROM gold_uc_fatura u
                          WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(e.NUM_UC_UCI AS VARCHAR))
                            AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                      )
                ),
                impacto_parcial AS (
                    SELECT
                        'Sobreposição parcial UC' AS tratamento,
                        0 AS ci_bruto_ganho,
                        SUM(GREATEST(
                            DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0
                            - DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0,
                            0
                        )) AS chi_bruto_ganho,
                        0 AS ci_liquido_ganho,
                        SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN GREATEST(
                            DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0
                            - DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0,
                            0
                        ) ELSE 0 END) AS chi_liquido_ganho
                    FROM adms_iqs_alterados a
                    WHERE ACAO_AJUSTE_PARCIAL = 'AJUSTAR_SOBREPOSICAO_PARCIAL_UC'
                      AND TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                      AND EXISTS (
                          SELECT 1 FROM gold_uc_fatura u
                          WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(a.NUM_UC_UCI AS VARCHAR))
                            AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                      )
                ),
                impacto_sem_uc AS (
                    SELECT
                        'Interrupção sem UC remanescente' AS tratamento,
                        COUNT(*) AS ci_bruto_ganho,
                        SUM(DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0) AS chi_bruto_ganho,
                        SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido_ganho,
                        SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                            THEN DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0 ELSE 0 END) AS chi_liquido_ganho
                    FROM adms_iqs_interrupcao_sem_uc_export e
                    WHERE TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                      AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                      AND DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) >= 180
                      AND EXISTS (
                          SELECT 1 FROM gold_uc_fatura u
                          WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(e.NUM_UC_UCI AS VARCHAR))
                            AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                      )
                ),
                impactos AS (
                    SELECT * FROM impacto_total
                    UNION ALL SELECT * FROM impacto_parcial
                    UNION ALL SELECT * FROM impacto_sem_uc
                )
                SELECT
                    tratamento,
                    COALESCE(chi_bruto_ganho, 0) / NULLIF(total_consumidores, 0) AS dec_bruto_ganho,
                    COALESCE(ci_bruto_ganho, 0) / NULLIF(total_consumidores, 0) AS fec_bruto_ganho,
                    COALESCE(chi_liquido_ganho, 0) / NULLIF(total_consumidores, 0) AS dec_liquido_ganho,
                    COALESCE(ci_liquido_ganho, 0) / NULLIF(total_consumidores, 0) AS fec_liquido_ganho,
                    COALESCE(chi_bruto_ganho, 0) AS chi_bruto_ganho,
                    COALESCE(ci_bruto_ganho, 0) AS ci_bruto_ganho,
                    COALESCE(chi_liquido_ganho, 0) AS chi_liquido_ganho,
                    COALESCE(ci_liquido_ganho, 0) AS ci_liquido_ganho
                FROM impactos
                CROSS JOIN denominador
                ORDER BY dec_bruto_ganho DESC
                """
            ).fetchdf().to_dict(orient="records")
            print("Query succeeded!", tratamentos)
        except Exception as e:
            print("Query failed!")
            print(e)

if __name__ == "__main__":
    run()

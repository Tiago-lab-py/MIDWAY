import duckdb
from pathlib import Path

def run():
    anomes = "202607"
    db_path = Path("data/processed") / f"iqs_adms_processed_{anomes}.duckdb"
    raw_path = Path("data/raw") / f"iqs_adms_raw_{anomes}.duckdb"
    
    print(f"Connecting to {db_path}...")
    with duckdb.connect(str(db_path), read_only=True) as con:
        print("Attaching raw...")
        raw_db_path_str = "'" + str(raw_path).replace("\\", "/").replace("'", "''") + "'"
        con.execute(f"ATTACH {raw_db_path_str} AS raw_db (READ_ONLY)")
        print("Executing query...")
        try:
            row = con.execute(
                """
                WITH denominador AS (
                    SELECT MAX(UC_FATURADA) AS total_consumidores
                    FROM gold_consumidores
                    WHERE REGIONAL_TOTAL = 'COPEL'
                ),
                raw_base AS (
                    SELECT
                        CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                        CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
                        CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS NUM_UC_UCI,
                        CAST(r.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR) AS TIPO_PROTOC_JUSTIF_UCI,
                        DATE_DIFF(
                            'second',
                            r.DATA_HORA_INIC_INTRP_ULT_HIADMS,
                            r.DATA_HORA_FIM_INTRP_ULT_HIADMS
                        ) / 3600.0 AS DURACAO_HORA
                    FROM raw_db.hiadms_raw r
                    WHERE r.DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
                      AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
                      AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS >= r.DATA_HORA_INIC_INTRP_ULT_HIADMS
                      AND TRIM(CAST(r.ESTADO_INTRP_ULT_HIADMS AS VARCHAR)) = '4'
                      AND DATE_DIFF(
                            'second',
                            r.DATA_HORA_INIC_INTRP_ULT_HIADMS,
                            r.DATA_HORA_FIM_INTRP_ULT_HIADMS
                        ) >= 180
                      AND EXISTS (
                          SELECT 1
                          FROM gold_uc_fatura u
                          WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR))
                            AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                      )
                ),
                pos AS (
                    SELECT
                        SUM(COALESCE(CI_BRUTO, 0)) AS ci_bruto,
                        SUM(COALESCE(CHI_BRUTO, 0)) AS chi_bruto,
                        SUM(COALESCE(CI_LIQUIDO, 0)) AS ci_liquido,
                        SUM(COALESCE(CHI_LIQUIDO, 0)) AS chi_liquido,
                        COUNT(*) AS linhas_bdo
                    FROM gold_apuracao_previa
                ),
                raw_agg AS (
                    SELECT
                        COUNT(*) AS ci_bruto,
                        SUM(DURACAO_HORA) AS chi_bruto,
                        SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido,
                        SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN DURACAO_HORA ELSE 0 END) AS chi_liquido,
                        COUNT(*) AS linhas_raw,
                        COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS ocorrencias_raw,
                        COUNT(DISTINCT NUM_SEQ_INTRP) AS interrupcoes_raw,
                        COUNT(DISTINCT NUM_UC_UCI) AS ucs_raw
                    FROM raw_base
                )
                SELECT
                    r.chi_bruto / NULLIF(d.total_consumidores, 0) AS dec_bruto_antes,
                    r.ci_bruto / NULLIF(d.total_consumidores, 0) AS fec_bruto_antes,
                    p.chi_bruto / NULLIF(d.total_consumidores, 0) AS dec_bruto_depois,
                    p.ci_bruto / NULLIF(d.total_consumidores, 0) AS fec_bruto_depois,
                    r.chi_liquido / NULLIF(d.total_consumidores, 0) AS dec_liquido_antes,
                    r.ci_liquido / NULLIF(d.total_consumidores, 0) AS fec_liquido_antes,
                    p.chi_liquido / NULLIF(d.total_consumidores, 0) AS dec_liquido_depois,
                    p.ci_liquido / NULLIF(d.total_consumidores, 0) AS fec_liquido_depois,
                    r.chi_bruto AS chi_bruto_antes,
                    r.ci_bruto AS ci_bruto_antes,
                    p.chi_bruto AS chi_bruto_depois,
                    p.ci_bruto AS ci_bruto_depois,
                    r.chi_liquido AS chi_liquido_antes,
                    r.ci_liquido AS ci_liquido_antes,
                    p.chi_liquido AS chi_liquido_depois,
                    p.ci_liquido AS ci_liquido_depois,
                    r.ocorrencias_raw,
                    r.interrupcoes_raw,
                    r.ucs_raw,
                    r.linhas_raw,
                    p.linhas_bdo,
                    d.total_consumidores
                FROM raw_agg r
                CROSS JOIN pos p
                CROSS JOIN denominador d
                """
            ).fetchone()
            print("Query succeeded!", row)
        except Exception as e:
            print("Query failed!")
            print(e)

if __name__ == "__main__":
    run()

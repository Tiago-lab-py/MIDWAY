import duckdb
from pathlib import Path

db_path = Path("data/processed/iqs_adms_processed_202607.duckdb")
raw_path = Path("data/raw/iqs_adms_raw_202607.duckdb")

def _table_exists(c, table):
    return c.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'").fetchone()[0] > 0

with duckdb.connect(str(db_path), read_only=True) as con:
    con.execute(f"ATTACH '{raw_path}' AS raw_db (READ_ONLY)")
    has_sem_uc = _table_exists(con, "adms_iqs_interrupcao_sem_uc_export")
    sem_uc_from = "adms_iqs_interrupcao_sem_uc_export e" if has_sem_uc else "(SELECT CAST(NULL AS TIMESTAMP) AS DTHR_INICIO_INTRP_UC, CAST(NULL AS TIMESTAMP) AS DATA_HORA_FIM_INTRP, CAST(NULL AS VARCHAR) AS NUM_UC_UCI, CAST(NULL AS VARCHAR) AS TIPO_PROTOC_JUSTIF_UCI WHERE 1=0) e"
    
    print("Executando tratamentos_sql...")
    sql = f"""
            WITH denominador AS (
                SELECT MAX(UC_FATURADA) AS total_consumidores
                FROM gold_consumidores
                WHERE REGIONAL_TOTAL = 'COPEL'
            ),
            intrp_total_ucs AS (
                SELECT 
                    CAST(NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
                    COUNT(*) AS total_ucs
                FROM raw_db.hiadms_raw r
                WHERE r.DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
                  AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
                  AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS >= r.DATA_HORA_INIC_INTRP_ULT_HIADMS
                  AND TRIM(CAST(r.ESTADO_INTRP_ULT_HIADMS AS VARCHAR)) = '4'
                GROUP BY CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR)
            ),
            intrp_ucs_91_d AS (
                SELECT 
                    NUM_SEQ_INTRP,
                    COUNT(*) AS ucs_91_d
                FROM adms_iqs_alterados
                WHERE ACAO_SOBREPOSICAO_TOTAL_UC = 'CLASSIFICAR_91_UC_CONTIDA'
                GROUP BY NUM_SEQ_INTRP
            ),
            interrupcoes_sem_uc AS (
                SELECT t.NUM_SEQ_INTRP
                FROM intrp_total_ucs t
                JOIN intrp_ucs_91_d a ON a.NUM_SEQ_INTRP = t.NUM_SEQ_INTRP
                WHERE a.ucs_91_d = t.total_ucs
            ),
            impacto_total AS (
                SELECT
                    'Sobreposição total UC' AS tratamento,
                    COUNT(*) AS ci_bruto_ganho,
                    SUM(DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0) AS chi_bruto_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                        THEN DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0 ELSE 0 END) AS chi_liquido_ganho
                FROM adms_iqs_alterados a
                WHERE ACAO_SOBREPOSICAO_TOTAL_UC = 'CLASSIFICAR_91_UC_CONTIDA'
                  AND NUM_SEQ_INTRP NOT IN (SELECT NUM_SEQ_INTRP FROM interrupcoes_sem_uc)
                  AND TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP)
                  AND DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) >= 180
                  AND EXISTS (
                      SELECT 1 FROM gold_uc_fatura u
                      WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(a.NUM_UC_UCI AS VARCHAR))
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
                    SUM(DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0) AS chi_bruto_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                        THEN DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0 ELSE 0 END) AS chi_liquido_ganho
                FROM {sem_uc_from}
                WHERE TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) IS NOT NULL
            ),
            outros_impactos AS (
                SELECT
                    CASE 
                        WHEN ACAO_REDIREC_MANOBRA_ESTADO_7 = 'REDIRECIONAR_MANOBRA_ESTADO_7' THEN 'Identificadas como Manobra ou Remanejamento'
                        ELSE 'Outras Classificações 91 (Total/Parcial/Geral)'
                    END AS tratamento,
                    COUNT(*) AS ci_bruto_ganho,
                    SUM(DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0) AS chi_bruto_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                        THEN DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0 ELSE 0 END) AS chi_liquido_ganho
                FROM adms_iqs_alterados a
                WHERE (
                       ACAO_REDIREC_MANOBRA_ESTADO_7 = 'REDIRECIONAR_MANOBRA_ESTADO_7'
                       OR (CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR) = '91' AND ACAO_REDIREC_MANOBRA_ESTADO_7 IS NULL)
                      )
                  AND TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP)
                  AND DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) >= 180
                  AND EXISTS (
                      SELECT 1 FROM gold_uc_fatura u
                      WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(a.NUM_UC_UCI AS VARCHAR))
                        AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                  )
            ),
            impactos AS (
                SELECT * FROM impacto_total
                UNION ALL SELECT * FROM impacto_parcial
                UNION ALL SELECT * FROM impacto_sem_uc
                UNION ALL SELECT * FROM outros_impactos
            )
            SELECT * FROM impactos
    """
    try:
        res = con.execute(sql).fetchall()
        print(f"Sucesso! {len(res)} linhas retornadas.")
    except Exception as e:
        print(f"Erro: {e}")

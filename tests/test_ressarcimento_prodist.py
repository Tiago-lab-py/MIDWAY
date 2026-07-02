import unittest

from tests.utils import TOLERANCIA_DECIMAL, conectar


class TestRessarcimentoProdist(unittest.TestCase):
    def setUp(self):
        self.con = conectar()

    def tearDown(self):
        self.con.close()

    def test_ressarcimento_tem_mesma_quantidade_da_continuidade(self):
        continuidade = self.con.execute("SELECT COUNT(*) FROM gold_continuidade_uc").fetchone()[0]
        prodist = self.con.execute("SELECT COUNT(*) FROM gold_ressarcimento_prodist").fetchone()[0]
        self.assertEqual(prodist, continuidade)

    def test_comp_geral_e_maior_valor_dic_fic_dmic(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_ressarcimento_prodist
            WHERE ABS(
                COMP_GERAL_CONTINUIDADE_PRODIST
                - GREATEST(
                    COALESCE(COMP_DIC_PRODIST, 0),
                    COALESCE(COMP_FIC_PRODIST, 0),
                    COALESCE(COMP_DMIC_PRODIST, 0)
                )
            ) > 0.001
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_compensacao_positiva_respeita_piso(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_ressarcimento_prodist
            WHERE (COMP_DIC_PRODIST > 0 AND COMP_DIC_PRODIST < 0.01)
               OR (COMP_FIC_PRODIST > 0 AND COMP_FIC_PRODIST < 0.01)
               OR (COMP_DMIC_PRODIST > 0 AND COMP_DMIC_PRODIST < 0.01)
               OR (COMP_DICRI_PRODIST > 0 AND COMP_DICRI_PRODIST < 0.01)
               OR (COMP_DISE_PRODIST > 0 AND COMP_DISE_PRODIST < 0.01)
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_compensacao_por_indicador_respeita_teto_18_vrc(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_ressarcimento_prodist
            WHERE COALESCE(VRC, 0) > 0
              AND (
                    COMP_DIC_PRODIST > 18 * VRC + 0.001
                 OR COMP_FIC_PRODIST > 18 * VRC + 0.001
                 OR COMP_DMIC_PRODIST > 18 * VRC + 0.001
                 OR COMP_DICRI_PRODIST > 18 * VRC + 0.001
                 OR COMP_DISE_PRODIST > 18 * VRC + 0.001
              )
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_formula_fic_prodist(self):
        total = self.con.execute(
            """
            WITH calc AS (
                SELECT
                    COMP_FIC_BRUTA_PRODIST,
                    CASE
                        WHEN FATURADA = 'S'
                         AND COALESCE(VRC, 0) > 0
                         AND COALESCE(META_FIC, 0) > 0
                         AND COALESCE(META_DIC, 0) > 0
                         AND COALESCE(FIC_BASE_COMPENSACAO, 0) > META_FIC
                        THEN (COALESCE(FIC_BASE_COMPENSACAO, 0) / META_FIC)
                             * META_DIC
                             * COALESCE(VRC, 0)
                             / 730.0
                             * COALESCE(KEI1_CONTINUIDADE, 0)
                        ELSE 0
                    END AS ESPERADO
                FROM gold_ressarcimento_prodist
            )
            SELECT COUNT(*)
            FROM calc
            WHERE ABS(COALESCE(COMP_FIC_BRUTA_PRODIST, 0) - COALESCE(ESPERADO, 0)) > 0.001
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_total_prodist_fecha_componentes(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_ressarcimento_prodist
            WHERE ABS(
                COMP_TOTAL_PRODIST
                - (
                    COALESCE(COMP_GERAL_CONTINUIDADE_PRODIST, 0)
                  + COALESCE(COMP_DICRI_PRODIST, 0)
                  + COALESCE(COMP_DISE_PRODIST, 0)
                )
            ) > 0.001
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_base_compensacao_exclui_comp52_e_posto_particular(self):
        total = self.con.execute(
            """
            WITH uc_unica_acessante AS (
                SELECT
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(NUM_OPER_CHV_INTRP AS VARCHAR) AS NUM_OPER_CHV_INTRP,
                    MIN(CAST(NUM_UC_UCI AS VARCHAR)) AS UC
                FROM gold_interrupcao_tratada
                WHERE TRIM(CAST(INDIC_PROPR_CHVP_INTRP AS VARCHAR)) = 'P'
                  AND TRIM(CAST(UC_ACESSANTE AS VARCHAR)) = 'S'
                  AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
                GROUP BY
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                    CAST(NUM_SEQ_INTRP AS VARCHAR),
                    CAST(NUM_OPER_CHV_INTRP AS VARCHAR)
                HAVING COUNT(DISTINCT CAST(NUM_UC_UCI AS VARCHAR)) = 1
            ),
            uc_acessante AS (
                SELECT DISTINCT
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(NUM_UC_UCI AS VARCHAR) AS UC
                FROM gold_interrupcao_tratada
                WHERE TRIM(CAST(UC_ACESSANTE AS VARCHAR)) = 'S'
                  AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            ),
            eventos_sem_compensacao AS (
                SELECT
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(NUM_INTRP_UCI AS VARCHAR) AS NUM_INTRP_UCI,
                    CAST(NUM_POSTO_UCI AS VARCHAR) AS NUM_POSTO_UCI,
                    CAST(NUM_UC_UCI AS VARCHAR) AS UC,
                    MAX(CASE WHEN TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) = '52' THEN 1 ELSE 0 END) AS TEM_COMP52,
                    MAX(CASE WHEN TRIM(CAST(INDIC_PROPR_POSTO_INTRP AS VARCHAR)) = 'P' THEN 1 ELSE 0 END) AS TEM_POSTO_PARTICULAR
                FROM gold_interrupcao_tratada
                WHERE NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
                GROUP BY
                    CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                    CAST(NUM_SEQ_INTRP AS VARCHAR),
                    CAST(NUM_INTRP_UCI AS VARCHAR),
                    CAST(NUM_POSTO_UCI AS VARCHAR),
                    CAST(NUM_UC_UCI AS VARCHAR)
            ),
            esperado AS (
                SELECT
                    CAST(a.NUM_UC_UCI AS VARCHAR) AS UC,
                    SUM(
                        CASE
                            WHEN TRIM(CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                             AND UPPER(TRIM(CAST(a.INTERRUPCAO_LONGA AS VARCHAR))) IN ('SIM', 'TRUE', '1')
                             AND UPPER(TRIM(CAST(a.INTERRUPCAO_CONTABILIZAVEL AS VARCHAR))) IN ('SIM', 'TRUE', '1')
                             AND u.UC IS NULL
                             AND ua.UC IS NULL
                             AND COALESCE(e.TEM_COMP52, 0) = 0
                             AND COALESCE(e.TEM_POSTO_PARTICULAR, 0) = 0
                            THEN COALESCE(TRY_CAST(a.DURACAO_HORA AS DOUBLE), 0)
                            ELSE 0
                        END
                    ) AS DIC_BASE_ESPERADA,
                    SUM(
                        CASE
                            WHEN TRIM(CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                             AND UPPER(TRIM(CAST(a.INTERRUPCAO_LONGA AS VARCHAR))) IN ('SIM', 'TRUE', '1')
                             AND UPPER(TRIM(CAST(a.INTERRUPCAO_CONTABILIZAVEL AS VARCHAR))) IN ('SIM', 'TRUE', '1')
                             AND u.UC IS NULL
                             AND ua.UC IS NULL
                             AND COALESCE(e.TEM_COMP52, 0) = 0
                             AND COALESCE(e.TEM_POSTO_PARTICULAR, 0) = 0
                            THEN 1
                            ELSE 0
                        END
                    ) AS FIC_BASE_ESPERADA,
                    MAX(
                        CASE
                            WHEN TRIM(CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                             AND UPPER(TRIM(CAST(a.INTERRUPCAO_LONGA AS VARCHAR))) IN ('SIM', 'TRUE', '1')
                             AND UPPER(TRIM(CAST(a.INTERRUPCAO_CONTABILIZAVEL AS VARCHAR))) IN ('SIM', 'TRUE', '1')
                             AND u.UC IS NULL
                             AND ua.UC IS NULL
                             AND COALESCE(e.TEM_COMP52, 0) = 0
                             AND COALESCE(e.TEM_POSTO_PARTICULAR, 0) = 0
                            THEN COALESCE(TRY_CAST(a.DURACAO_HORA AS DOUBLE), 0)
                            ELSE 0
                        END
                    ) AS DMIC_BASE_ESPERADA
                FROM gold_apuracao_uc a
                LEFT JOIN uc_unica_acessante u
                  ON u.NUM_OCORRENCIA_ADMS = CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)
                 AND u.NUM_SEQ_INTRP = CAST(a.NUM_SEQ_INTRP AS VARCHAR)
                 AND u.UC = CAST(a.NUM_UC_UCI AS VARCHAR)
                LEFT JOIN uc_acessante ua
                  ON ua.NUM_OCORRENCIA_ADMS = CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)
                 AND ua.NUM_SEQ_INTRP = CAST(a.NUM_SEQ_INTRP AS VARCHAR)
                 AND ua.UC = CAST(a.NUM_UC_UCI AS VARCHAR)
                LEFT JOIN eventos_sem_compensacao e
                  ON e.NUM_OCORRENCIA_ADMS = CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)
                 AND e.NUM_SEQ_INTRP = CAST(a.NUM_SEQ_INTRP AS VARCHAR)
                 AND e.NUM_INTRP_UCI = CAST(a.NUM_INTRP_UCI AS VARCHAR)
                 AND e.NUM_POSTO_UCI = CAST(a.NUM_POSTO_UCI AS VARCHAR)
                 AND e.UC = CAST(a.NUM_UC_UCI AS VARCHAR)
                GROUP BY CAST(a.NUM_UC_UCI AS VARCHAR)
            )
            SELECT COUNT(*)
            FROM gold_continuidade_uc c
            JOIN esperado e
              ON e.UC = c.UC
            WHERE ABS(COALESCE(c.DIC_BASE_COMPENSACAO, 0) - COALESCE(e.DIC_BASE_ESPERADA, 0)) > 0.001
               OR ABS(COALESCE(c.FIC_BASE_COMPENSACAO, 0) - COALESCE(e.FIC_BASE_ESPERADA, 0)) > 0.001
               OR ABS(COALESCE(c.DMIC_BASE_COMPENSACAO, 0) - COALESCE(e.DMIC_BASE_ESPERADA, 0)) > 0.001
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

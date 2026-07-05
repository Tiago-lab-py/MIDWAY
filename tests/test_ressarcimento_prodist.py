import unittest

from tests.utils import conectar


class TestRessarcimentoProdist(unittest.TestCase):
    def setUp(self):
        self.con = conectar()

    def tearDown(self):
        self.con.close()

    def test_ressarcimento_tem_mesma_quantidade_da_continuidade(self):
        continuidade = self.con.execute(
            "SELECT COUNT(*) FROM gold_continuidade_uc"
        ).fetchone()[0]
        prodist = self.con.execute(
            "SELECT COUNT(*) FROM gold_ressarcimento_prodist"
        ).fetchone()[0]
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
                         AND COALESCE(COMP52, 'N') <> 'S'
                         AND COALESCE(CAUSA71, 'N') <> 'S'
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

    def test_base_compensacao_nao_excede_indicadores_realizados(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_continuidade_uc
            WHERE COALESCE(DIC_BASE_COMPENSACAO, 0) > COALESCE(DIC, 0) + 0.001
               OR COALESCE(FIC_BASE_COMPENSACAO, 0) > COALESCE(FIC, 0) + 0.001
               OR COALESCE(DMIC_BASE_COMPENSACAO, 0) > COALESCE(DMIC, 0) + 0.001
               OR COALESCE(DICRI_BASE_COMPENSACAO, 0) > COALESCE(DIC_DICRI, 0) + 0.001
               OR COALESCE(DISE_BASE_COMPENSACAO, 0) > COALESCE(DIC_ISE, 0) + 0.001
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_comp52_e_causa71_sao_excluidos_dos_indicadores_realizados(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_continuidade_uc
            WHERE (
                    COALESCE(COMP52, 'N') = 'S'
                 OR COALESCE(CAUSA71, 'N') = 'S'
              )
              AND (
                    COALESCE(DIC, 0) > COALESCE(DIC_BRT, 0) + 0.001
                 OR COALESCE(FIC, 0) > COALESCE(FIC_BRT, 0) + 0.001
                 OR COALESCE(DMIC, 0) > COALESCE(DMIC_BRT, 0) + 0.001
              )
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

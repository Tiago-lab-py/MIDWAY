import unittest

from tests.utils import TOLERANCIA_DECIMAL, conectar


class TestApuracaoDicFic(unittest.TestCase):
    def setUp(self):
        self.con = conectar()

    def tearDown(self):
        self.con.close()

    def test_motivo_tratamento_diferenciado_nao_entra_na_base_apuravel(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NOT NULL
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_dic_fic_dmic_respeitam_filtros_iqs_comp52_e_causa71(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_continuidade_uc
            WHERE COALESCE(DIC, 0) > COALESCE(DIC_BRT, 0) + 0.001
               OR COALESCE(FIC, 0) > COALESCE(FIC_BRT, 0) + 0.001
               OR COALESCE(DMIC, 0) > COALESCE(DMIC_BRT, 0) + 0.001
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_comp52_e_causa71_estao_marcados_para_auditoria(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_continuidade_uc
            WHERE COALESCE(COMP52, 'N') = 'S'
               OR COALESCE(CAUSA71, 'N') = 'S'
               OR COALESCE(COMP52_CAUSA71, 'N') = 'S'
            """
        ).fetchone()[0]
        self.assertGreater(total, 0)

    def test_apuracao_previa_fecha_com_base_uc(self):
        ci_previa, chi_previa = self.con.execute(
            "SELECT SUM(CI_LIQUIDO), SUM(CHI_LIQUIDO) FROM gold_apuracao_previa"
        ).fetchone()
        ci_uc, chi_uc = self.con.execute(
            "SELECT SUM(CI_LIQUIDO), SUM(CHI_LIQUIDO) FROM gold_apuracao_uc"
        ).fetchone()

        self.assertEqual(ci_previa, ci_uc)
        self.assertAlmostEqual(chi_previa, chi_uc, delta=TOLERANCIA_DECIMAL)

    def test_manobra_nao_entra_na_base_apuravel(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

    def test_datas_e_duracoes_validas(self):
        total = self.con.execute(
            """
            SELECT COUNT(*)
            FROM gold_apuracao_uc
            WHERE DTHR_INICIO_INTRP_UC IS NULL
               OR DATA_HORA_FIM_INTRP IS NULL
               OR DATA_HORA_FIM_INTRP < DTHR_INICIO_INTRP_UC
               OR DURACAO_HORA < 0
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)
import unittest

from tests.utils import coluna_existe, conectar, escalar, tabela_existe


class TestContratosTabelas(unittest.TestCase):
    def setUp(self):
        self.con = conectar()

    def tearDown(self):
        self.con.close()

    def test_tabelas_obrigatorias_existem_e_tem_linhas(self):
        tabelas = [
            "silver_iqs_uc_fatura",
            "silver_iqs_vrc",
            "silver_iqs_metas_uc",
            "silver_interrupcao_tratada",
            "silver_interrupcao_uc_apuravel",
            "gold_apuracao_uc",
            "gold_apuracao_previa",
            "gold_continuidade_uc",
            "gold_ressarcimento_prodist",
            "gold_interrupcao_sem_uc",
            "gold_ocorrencia_sem_uc",
        ]
        for tabela in tabelas:
            with self.subTest(tabela=tabela):
                self.assertTrue(tabela_existe(self.con, tabela))
                self.assertGreater(escalar(self.con, f"SELECT COUNT(*) FROM {tabela}"), 0)

    def test_colunas_obrigatorias_apuracao_uc(self):
        colunas = [
            "NUM_UC_UCI",
            "NUM_SEQ_INTRP",
            "COD_TIPO_INTRP",
            "TIPO_PROTOC_JUSTIF_UCI",
            "NUM_MOTIVO_TRAT_DIF_UCI",
            "DTHR_INICIO_INTRP_UC",
            "DATA_HORA_FIM_INTRP",
            "DURACAO_HORA",
            "CI_LIQUIDO",
            "CHI_LIQUIDO",
        ]
        for coluna in colunas:
            with self.subTest(coluna=coluna):
                self.assertTrue(coluna_existe(self.con, "gold_apuracao_uc", coluna))

    def test_colunas_obrigatorias_ressarcimento_prodist(self):
        colunas = [
            "UC",
            "VRC",
            "META_DIC",
            "META_FIC",
            "META_DMIC",
            "KEI1_CONTINUIDADE",
            "COMP_DIC_PRODIST",
            "COMP_FIC_PRODIST",
            "COMP_DMIC_PRODIST",
            "COMP_GERAL_CONTINUIDADE_PRODIST",
            "COMP_TOTAL_PRODIST",
            "STATUS_CALCULO_PRODIST",
            "COMP52",
            "POSTO_PARTICULAR",
        ]
        for coluna in colunas:
            with self.subTest(coluna=coluna):
                self.assertTrue(coluna_existe(self.con, "gold_ressarcimento_prodist", coluna))

    def test_colunas_obrigatorias_ocorrencia_sem_uc(self):
        colunas = [
            "NUM_OCORRENCIA_ADMS",
            "QTD_INTERRUPCOES_ESTADO_4",
            "QTD_INTERRUPCOES_SEM_UC_APURAVEL",
            "QTD_UCS_APURAVEIS",
            "OCORRENCIA_SEM_UC_APURAVEL",
            "ACAO_SUGERIDA_AUDITORIA",
        ]
        for coluna in colunas:
            with self.subTest(coluna=coluna):
                self.assertTrue(coluna_existe(self.con, "gold_ocorrencia_sem_uc", coluna))

    def test_cod_tipo_intrp_usa_dominio_esperado(self):
        total = escalar(
            self.con,
            """
            SELECT COUNT(*)
            FROM gold_apuracao_uc
            WHERE TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) NOT IN ('1', '2', '3')
            """,
        )
        self.assertEqual(total, 0)

    def test_tipo_protoc_justif_uci_usa_dominio_esperado(self):
        total = escalar(
            self.con,
            """
            SELECT COUNT(*)
            FROM gold_apuracao_uc
            WHERE TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) NOT IN ('0', '1', '5', '6')
            """,
        )
        self.assertEqual(total, 0)

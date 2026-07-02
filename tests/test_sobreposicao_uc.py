import unittest

from tests.utils import conectar


class TestSobreposicaoUc(unittest.TestCase):
    def setUp(self):
        self.con = conectar()

    def tearDown(self):
        self.con.close()

    def test_sem_sobreposicao_residual_por_uc_e_tipo_na_base_liquida(self):
        total = self.con.execute(
            """
            WITH base AS (
                SELECT
                    TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS UC,
                    TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) AS COD_TIPO_INTRP,
                    TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) AS TIPO_PROTOC_JUSTIF_UCI,
                    TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                    DTHR_INICIO_INTRP_UC,
                    DATA_HORA_FIM_INTRP,
                    LAG(DATA_HORA_FIM_INTRP) OVER (
                        PARTITION BY
                            TRIM(CAST(NUM_UC_UCI AS VARCHAR)),
                            TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)),
                            TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR))
                        ORDER BY
                            DTHR_INICIO_INTRP_UC,
                            DATA_HORA_FIM_INTRP,
                            TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                    ) AS FIM_ANTERIOR
                FROM gold_apuracao_uc
                WHERE CI_LIQUIDO = 1
                  AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            )
            SELECT COUNT(*)
            FROM base
            WHERE FIM_ANTERIOR > DTHR_INICIO_INTRP_UC
            """
        ).fetchone()[0]
        self.assertEqual(total, 0)

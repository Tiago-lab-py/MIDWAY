import unittest

from midway.v7.generate_real_anomalies import _anomaly, _str_or_none, stable_uuid


class V7RealAnomaliesTest(unittest.TestCase):
    def test_stable_uuid_is_deterministic(self):
        self.assertEqual(stable_uuid("RAW:1"), stable_uuid("RAW:1"))
        self.assertNotEqual(stable_uuid("RAW:1"), stable_uuid("RAW:2"))

    def test_anomaly_contract_uses_real_pipeline_origin(self):
        anomaly = _anomaly(
            key="TESTE_REAL:1",
            code="OUTLIER_BRUTO",
            name="Teste real",
            category="integridade",
            severity="alta",
            confidence=0.9,
            status="PENDENTE",
            origin="RAW/SILVER",
            occurrence="1-1",
            interruption="123",
            regional="LES",
            uc=None,
            equipment="EQP",
            description="Registro real de teste.",
            simple="Explicação simples.",
            technical="Explicação técnica.",
            rule="regra_real",
            impact_text="Impacto real.",
            fields=["CAMPO"],
            original={"CAMPO": "A"},
            suggested={"CAMPO": "B"},
            impact={"dic": 1, "fic": 1, "dec": 0, "fec": 0, "ressarcimento": 0},
            evidence=[("CAMPO", "A", "RAW")],
            suggestion_action="revisar",
            suggestion_original="A",
            suggestion_value="B",
            suggestion_reason="Base real sinalizada.",
        )

        self.assertEqual(anomaly["origem"], "RAW/SILVER")
        self.assertEqual(anomaly["anomalia_codigo"], "OUTLIER_BRUTO")
        self.assertTrue(anomaly["evidencias"])
        self.assertTrue(anomaly["sugestao"]["requer_aprovacao"])

    def test_str_or_none_filters_nan_text(self):
        self.assertIsNone(_str_or_none(None))
        self.assertIsNone(_str_or_none("nan"))
        self.assertEqual(_str_or_none(123), "123")


if __name__ == "__main__":
    unittest.main()

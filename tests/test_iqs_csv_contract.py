import pandas as pd

from midway.export.iqs_csv import exportar_dataframe_iqs


def test_exportar_dataframe_iqs_aplica_contrato_rigido(tmp_path):
    caminho = tmp_path / "Interrupcoes_IQS_20260714101010_TESTE.CSV"
    df = pd.DataFrame(
        [
            {
                "DATA_HORA_INIC_INTRP": pd.Timestamp("2026-07-14 08:09:10"),
                "DATA_HORA_FIM_INTRP": "2026-07-14 09:10:11",
                "DTHR_INICIO_INTRP_UC": "14/07/2026 08:15",
                "NUM_INTRP_INIC_MANOBRA_UCI": "123.0",
                "NUM_GEO_CHV_INTRP": 456.0,
                "DESC_INTRP": "Tensão – área crítica",
                "CAMPO_VAZIO": "",
            }
        ]
    )

    exportar_dataframe_iqs(df, caminho)

    conteudo = caminho.read_bytes()
    assert b"\r\n" not in conteudo
    texto = conteudo.decode("iso-8859-1")
    assert "|" in texto.splitlines()[0]
    assert "14/07/2026 08:09:10" in texto
    assert "14/07/2026 09:10:11" in texto
    assert "14/07/2026 08:15:00" in texto
    assert "123" in texto
    assert "456" in texto
    assert "Tensão - área crítica" in texto
    assert texto.endswith("\n")

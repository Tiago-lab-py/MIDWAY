import csv
import unicodedata

import pandas as pd


IQS_CSV_ENCODING = "iso-8859-1"
IQS_CSV_SEPARATOR = "|"
IQS_CSV_LINE_TERMINATOR = "\n"

TRANSLITERACAO_CARACTERES_ESPECIAIS = str.maketrans(
    {
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u2033": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2022": "-",
        "\u2026": "...",
        "\u2122": "TM",
        "\u00ae": "(R)",
        "\u00a9": "(C)",
    }
)


def transliterar_iso_8859_1(valor):
    if pd.isna(valor):
        return " "

    texto = str(valor)
    if texto == "":
        return " "

    texto = texto.translate(TRANSLITERACAO_CARACTERES_ESPECIAIS)

    try:
        texto.encode(IQS_CSV_ENCODING)
        return texto
    except UnicodeEncodeError:
        texto_normalizado = unicodedata.normalize("NFKD", texto)
        texto_sem_combinantes = "".join(
            caractere
            for caractere in texto_normalizado
            if not unicodedata.combining(caractere)
        )
        return texto_sem_combinantes.encode(
            IQS_CSV_ENCODING,
            errors="replace",
        ).decode(IQS_CSV_ENCODING)


def preparar_dataframe_iqs(df):
    df = df.astype("object").where(pd.notna(df), " ")
    df = df.replace("", " ")
    return df.apply(lambda coluna: coluna.map(transliterar_iso_8859_1))


def exportar_dataframe_iqs(df, caminho_csv):
    df = preparar_dataframe_iqs(df)
    df.to_csv(
        caminho_csv,
        sep=IQS_CSV_SEPARATOR,
        index=False,
        na_rep=" ",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator=IQS_CSV_LINE_TERMINATOR,
        encoding=IQS_CSV_ENCODING,
    )

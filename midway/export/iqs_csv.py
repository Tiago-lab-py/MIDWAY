import csv
import unicodedata
from datetime import datetime

import pandas as pd


IQS_CSV_ENCODING = "iso-8859-1"
IQS_CSV_SEPARATOR = "|"
IQS_CSV_LINE_TERMINATOR = "\n"
IQS_DATE_TIME_COLUMNS = {
    "DATA_HORA_INIC_INTRP",
    "DATA_HORA_FIM_INTRP",
    "DTHR_INICIO_INTRP_UC",
}
IQS_INTEGER_COLUMNS = {
    "NUM_INTRP_INIC_MANOBRA_UCI",
    "NUM_GEO_CHV_INTRP",
}
IQS_DATE_TIME_INPUT_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S.%f",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%m/%d/%Y %H:%M:%S.%f",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
)

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


def normalizar_data_hora_iqs(valor):
    if pd.isna(valor):
        return valor

    texto = str(valor).strip()
    if not texto:
        return texto

    for formato in IQS_DATE_TIME_INPUT_FORMATS:
        try:
            data = datetime.strptime(texto, formato)
            return data.strftime("%d/%m/%Y %H:%M:%S")
        except ValueError:
            continue

    return valor


def normalizar_campos_iqs(df):
    df = df.copy()

    for coluna in IQS_DATE_TIME_COLUMNS:
        if coluna not in df.columns:
            continue

        if pd.api.types.is_datetime64_any_dtype(df[coluna]):
            df[coluna] = df[coluna].dt.strftime("%d/%m/%Y %H:%M:%S")
            continue

        df[coluna] = df[coluna].map(normalizar_data_hora_iqs)

    for coluna in IQS_INTEGER_COLUMNS:
        if coluna not in df.columns:
            continue

        original = df[coluna].astype("string").fillna("").str.strip()
        sem_vazio = original.replace("", pd.NA)
        numerico = pd.to_numeric(sem_vazio, errors="coerce")
        inteiro = numerico.round()
        mascara_inteiro = numerico.notna() & ((numerico - inteiro).abs() < 0.000000001)
        resultado = original.copy()
        resultado.loc[mascara_inteiro] = inteiro.loc[mascara_inteiro].astype("Int64").astype("string")
        df[coluna] = resultado

    return df


def preparar_dataframe_iqs(df):
    df = normalizar_campos_iqs(df)
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

from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from midway.export.iqs_csv import IQS_CSV_ENCODING, transliterar_iso_8859_1


BASE_DIR = Path("data")
EXPORT_DIR = BASE_DIR / "export"

PASTAS_EXPORTACOES_AUXILIARES = [
    EXPORT_DIR / "sobreposicao_total_uc",
    EXPORT_DIR / "sobreposicao_UC_parcial",
    EXPORT_DIR / "interrupcao_sem_uc",
]

FORMATOS_ENTRADA = [
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
]

HINTS_COLUNA_DATA = [
    "DATA",
    "DTHR",
    "DAT_",
    "DTA_",
]

COLUNAS_INTEIRAS = {
    "NUM_INTRP_INIC_MANOBRA_UCI",
    "NUM_GEO_CHV_INTRP",
}
TIMESTAMP_ARQUIVO_RE = re.compile(r"_(\d{14})_")


def coluna_de_data(nome_coluna: str) -> bool:
    nome = nome_coluna.upper()
    return any(hint in nome for hint in HINTS_COLUNA_DATA)


def coluna_inteira(nome_coluna: str) -> bool:
    return nome_coluna.upper() in COLUNAS_INTEIRAS


def detectar_delimitador(caminho: Path) -> str:
    texto = ler_texto_csv(caminho)[:4096]
    if "|" in texto:
        return "|"
    if ";" in texto:
        return ";"
    return ","


def ler_texto_csv(caminho: Path) -> str:
    for encoding in ("utf-8-sig", IQS_CSV_ENCODING):
        try:
            return caminho.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    return caminho.read_text(encoding=IQS_CSV_ENCODING, errors="replace")


def converter_data(valor: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        return " "

    for formato in FORMATOS_ENTRADA:
        try:
            data = datetime.strptime(valor, formato)
            if "%H" in formato:
                return data.strftime("%d/%m/%Y %H:%M:%S")
            return data.strftime("%d/%m/%Y")
        except ValueError:
            continue

    return valor


def converter_inteiro(valor: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        return " "

    try:
        numero = float(valor.replace(",", "."))
    except ValueError:
        return valor

    inteiro = round(numero)
    if abs(numero - inteiro) > 0.000000001:
        return valor

    return str(inteiro)


def normalizar_csv(caminho: Path) -> bool:
    delimitador = detectar_delimitador(caminho)
    texto = ler_texto_csv(caminho)

    linhas_texto = texto.splitlines()
    if not linhas_texto:
        return False

    reader = csv.DictReader(linhas_texto, delimiter=delimitador)
    linhas = list(reader)

    if not reader.fieldnames or not linhas:
        return False

    colunas_data = [col for col in reader.fieldnames if coluna_de_data(col)]
    colunas_inteiras = [col for col in reader.fieldnames if coluna_inteira(col)]

    if not colunas_data and not colunas_inteiras:
        return False

    alterou = False
    for linha in linhas:
        for coluna in colunas_data:
            original = linha.get(coluna, "")
            convertido = converter_data(original)
            if convertido != original:
                linha[coluna] = convertido
                alterou = True

        for coluna in colunas_inteiras:
            original = linha.get(coluna, "")
            convertido = converter_inteiro(original)
            if convertido != original:
                linha[coluna] = convertido
                alterou = True

        for coluna in reader.fieldnames:
            original = linha.get(coluna, "")
            if original is None or original == "":
                linha[coluna] = " "
                alterou = True
            else:
                convertido = transliterar_iso_8859_1(original)
                if convertido != original:
                    linha[coluna] = convertido
                    alterou = True

    if not alterou:
        return False

    with caminho.open("w", encoding=IQS_CSV_ENCODING, newline="") as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=reader.fieldnames,
            delimiter=delimitador,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(linhas)

    return True


def listar_csvs_mais_recentes(pasta: Path) -> list[Path]:
    arquivos = {
        caminho.resolve(): caminho
        for padrao in ("*.CSV", "*.csv")
        for caminho in pasta.glob(padrao)
    }.values()
    arquivos = list(arquivos)

    if not arquivos:
        return []

    timestamps = {
        caminho: TIMESTAMP_ARQUIVO_RE.search(caminho.name).group(1)
        for caminho in arquivos
        if TIMESTAMP_ARQUIVO_RE.search(caminho.name)
    }

    if not timestamps:
        mais_recente = max(arquivo.stat().st_mtime for arquivo in arquivos)
        return [arquivo for arquivo in arquivos if arquivo.stat().st_mtime == mais_recente]

    timestamp_mais_recente = max(timestamps.values())
    return [
        caminho
        for caminho, timestamp in timestamps.items()
        if timestamp == timestamp_mais_recente
    ]


def normalizar_datas_exportacoes_auxiliares() -> list[Path]:
    arquivos_alterados = []
    arquivos_bloqueados = []
    arquivos_removidos = []

    for pasta in PASTAS_EXPORTACOES_AUXILIARES:
        if not pasta.exists():
            continue

        arquivos = listar_csvs_mais_recentes(pasta)
        for caminho in arquivos:
            try:
                if not caminho.exists():
                    arquivos_removidos.append(caminho)
                    continue

                if normalizar_csv(caminho):
                    arquivos_alterados.append(caminho)
            except PermissionError:
                arquivos_bloqueados.append(caminho)
            except FileNotFoundError:
                arquivos_removidos.append(caminho)

    if arquivos_bloqueados:
        print("Aviso: alguns CSVs estavam abertos e nao foram normalizados:")
        for caminho in arquivos_bloqueados:
            print(f"- {caminho}")

    if arquivos_removidos:
        print("Aviso: alguns CSVs nao estavam mais disponiveis durante a normalizacao:")
        for caminho in arquivos_removidos:
            print(f"- {caminho}")

    return arquivos_alterados


def main():
    arquivos = normalizar_datas_exportacoes_auxiliares()

    if not arquivos:
        print("Nenhum CSV auxiliar precisou de normalizacao de data/inteiro.")
        return

    print("Datas e inteiros normalizados nos CSVs auxiliares:")
    for caminho in arquivos:
        print(f"- {caminho}")


if __name__ == "__main__":
    main()

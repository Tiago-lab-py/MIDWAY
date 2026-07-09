import csv
import sys
from datetime import datetime
from pathlib import Path


FORMATOS_ENTRADA = [
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
]

COLUNAS_DATA_HINTS = [
    "DATA",
    "DTHR",
    "DT_",
    "HORA",
]


def parece_coluna_data(nome: str) -> bool:
    nome_upper = nome.upper()
    return any(hint in nome_upper for hint in COLUNAS_DATA_HINTS)


def converter_valor(valor: str) -> str:
    valor = (valor or "").strip()
    if not valor:
        return valor

    for formato in FORMATOS_ENTRADA:
        try:
            data = datetime.strptime(valor, formato)
            if "H" in formato:
                return data.strftime("%d/%m/%Y %H:%M:%S")
            return data.strftime("%d/%m/%Y")
        except ValueError:
            pass

    return valor


def detectar_delimitador(caminho: Path) -> str:
    amostra = caminho.read_text(encoding="utf-8-sig", errors="ignore")[:4096]
    if "|" in amostra:
        return "|"
    if ";" in amostra:
        return ";"
    return ","


def corrigir_csv(caminho: Path) -> None:
    delimitador = detectar_delimitador(caminho)
    backup = caminho.with_suffix(caminho.suffix + ".bak")

    texto = caminho.read_text(encoding="utf-8-sig", errors="ignore")
    backup.write_text(texto, encoding="utf-8-sig", newline="")

    linhas = list(csv.DictReader(texto.splitlines(), delimiter=delimitador))
    if not linhas:
        print("CSV vazio.")
        return

    colunas = linhas[0].keys()
    colunas_data = [col for col in colunas if parece_coluna_data(col)]

    if not colunas_data:
        print("Nenhuma coluna de data detectada.")
        return

    for linha in linhas:
        for coluna in colunas_data:
            linha[coluna] = converter_valor(linha.get(coluna, ""))

    with caminho.open("w", encoding="utf-8-sig", newline="") as arquivo:
        writer = csv.DictWriter(
            arquivo,
            fieldnames=list(colunas),
            delimiter=delimitador,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(linhas)

    print(f"Arquivo corrigido: {caminho}")
    print(f"Backup criado: {backup}")
    print("Colunas tratadas:")
    for coluna in colunas_data:
        print(f"- {coluna}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python tools\\corrigir_datas_csv_exportado.py caminho_do_csv")

    corrigir_csv(Path(sys.argv[1]))


if __name__ == "__main__":
    main()
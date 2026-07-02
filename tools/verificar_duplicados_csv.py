from collections import defaultdict
from pathlib import Path


EXPORT_DIR = Path("data/export")
MARTS_DIR = Path("data/marts")


def contar_duplicados_linha_inteira(caminho_csv: Path):
    ocorrencias = defaultdict(lambda: {"qtd": 0, "primeira_linha": 0})

    with caminho_csv.open("rb") as arquivo:
        for numero_linha, linha in enumerate(arquivo, start=1):
            linha_normalizada = linha.rstrip(b"\r\n")

            if numero_linha == 1:
                continue

            item = ocorrencias[linha_normalizada]
            item["qtd"] += 1

            if item["primeira_linha"] == 0:
                item["primeira_linha"] = numero_linha

    duplicados = [
        {
            "arquivo": caminho_csv.name,
            "primeira_linha": dados["primeira_linha"],
            "qtd_ocorrencias": dados["qtd"],
            "qtd_duplicadas": dados["qtd"] - 1,
            "linha": linha.decode("utf-8-sig", errors="replace"),
        }
        for linha, dados in ocorrencias.items()
        if dados["qtd"] > 1
    ]

    return duplicados


def exportar_auditoria(duplicados, caminho_saida: Path):
    with caminho_saida.open("w", encoding="utf-8-sig", newline="\n") as arquivo:
        arquivo.write(
            "ARQUIVO|PRIMEIRA_LINHA|QTD_OCORRENCIAS|QTD_DUPLICADAS|LINHA_COMPLETA\n"
        )

        for item in duplicados:
            linha_csv = item["linha"].replace("\r", " ").replace("\n", " ")
            arquivo.write(
                f"{item['arquivo']}|"
                f"{item['primeira_linha']}|"
                f"{item['qtd_ocorrencias']}|"
                f"{item['qtd_duplicadas']}|"
                f"{linha_csv}\n"
            )


def exportar_resumo(total_arquivos, total_linhas_duplicadas, caminho_saida: Path):
    status = "OK" if total_linhas_duplicadas == 0 else "ERRO"

    with caminho_saida.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("AUDITORIA DE LINHAS DUPLICADAS NA EXPORTACAO IQS\n")
        arquivo.write(f"Status: {status}\n")
        arquivo.write(f"Pasta avaliada: {EXPORT_DIR}\n")
        arquivo.write(f"Arquivos avaliados: {total_arquivos}\n")
        arquivo.write(f"Linhas duplicadas encontradas: {total_linhas_duplicadas}\n")


def main():
    MARTS_DIR.mkdir(parents=True, exist_ok=True)

    arquivos_csv = sorted(EXPORT_DIR.glob("Interrupcoes_IQS_*.CSV"))

    if not arquivos_csv:
        raise RuntimeError(f"Nenhum CSV final encontrado em {EXPORT_DIR}")

    todos_duplicados = []

    for caminho_csv in arquivos_csv:
        print(f"Verificando duplicados: {caminho_csv}")
        todos_duplicados.extend(contar_duplicados_linha_inteira(caminho_csv))

    total_linhas_duplicadas = sum(item["qtd_duplicadas"] for item in todos_duplicados)

    caminho_auditoria = MARTS_DIR / "Auditoria_Duplicados_Linha_Inteira_Export.CSV"
    caminho_resumo = MARTS_DIR / "Auditoria_Duplicados_Linha_Inteira_Export_RESUMO.TXT"

    exportar_auditoria(todos_duplicados, caminho_auditoria)
    exportar_resumo(len(arquivos_csv), total_linhas_duplicadas, caminho_resumo)

    print(f"Auditoria exportada: {caminho_auditoria}")
    print(f"Resumo exportado: {caminho_resumo}")

    if total_linhas_duplicadas > 0:
        raise RuntimeError(
            f"Foram encontradas {total_linhas_duplicadas:,} linhas duplicadas."
        )

    print("OK: nenhuma linha 100% duplicada encontrada.")


if __name__ == "__main__":
    main()

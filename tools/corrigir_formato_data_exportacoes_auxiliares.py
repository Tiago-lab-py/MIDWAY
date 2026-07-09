from pathlib import Path


PASTAS = [
    Path("midway"),
    Path("tools"),
]

SUBSTITUICOES = {
    "%d/%m/%Y": "%d/%m/%Y",
    "%d/%m/%y": "%d/%m/%y",
    "DD/MM/YYYY": "DD/MM/YYYY",
    "dd/mm/yyyy": "dd/mm/yyyy",
    "dd/mm/aaaa": "dd/mm/aaaa",
}


def main():
    alterados = []

    for pasta in PASTAS:
        if not pasta.exists():
            continue

        for caminho in pasta.rglob("*.py"):
            texto = caminho.read_text(encoding="utf-8", errors="ignore")
            novo = texto

            for antigo, novo_valor in SUBSTITUICOES.items():
                novo = novo.replace(antigo, novo_valor)

            if novo != texto:
                caminho.write_text(novo, encoding="utf-8")
                alterados.append(str(caminho))

    if not alterados:
        print("Nenhum formato DD/MM/YYYY encontrado nos arquivos Python.")
        print("Se o problema continuar, a data pode estar sendo interpretada pelo Excel.")
        return

    print("Arquivos atualizados:")
    for arquivo in alterados:
        print(f"- {arquivo}")


if __name__ == "__main__":
    main()
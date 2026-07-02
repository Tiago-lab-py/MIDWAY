from pathlib import Path


PASTAS_PADRAO = [
    Path("data/export"),
]


def normalizar_linhas_unix(caminho_csv: Path) -> bool:
    conteudo = caminho_csv.read_bytes()
    normalizado = conteudo.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    if normalizado == conteudo:
        return False

    caminho_csv.write_bytes(normalizado)
    return True


def main():
    total = 0
    alterados = 0

    for pasta in PASTAS_PADRAO:
        if not pasta.exists():
            continue

        for caminho_csv in pasta.glob("*.CSV"):
            total += 1
            if normalizar_linhas_unix(caminho_csv):
                alterados += 1
                print(f"Normalizado LF: {caminho_csv}")

    print(f"CSVs avaliados: {total}")
    print(f"CSVs alterados: {alterados}")


if __name__ == "__main__":
    main()

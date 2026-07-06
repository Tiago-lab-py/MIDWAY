from pathlib import Path


MARCADOR_INICIO = "# >>> MIDWAY ISE POR JANELA"
MARCADOR_FIM = "# <<< MIDWAY ISE POR JANELA"

BLOCO = """

# >>> MIDWAY ISE POR JANELA
from midway.web.ise_janela_component import mostrar_simulacao_ise_por_janela


mostrar_simulacao_ise_por_janela()
# <<< MIDWAY ISE POR JANELA
"""


def encontrar_pagina() -> Path:
    candidatos = [
        Path("midway") / "web" / "pages" / "04_Simulacao_ISE.py",
        Path("pages") / "04_Simulacao_ISE.py",
        Path("04_Simulacao_ISE.py",
        ),
    ]
    for candidato in candidatos:
        if candidato.exists():
            return candidato
    raise FileNotFoundError(
        "Nao encontrei 04_Simulacao_ISE.py. Execute este script na raiz do projeto D:\\MIDWAY_novo."
    )


def substituir_bloco(texto: str) -> str:
    if MARCADOR_INICIO not in texto:
        return texto.rstrip() + BLOCO

    inicio = texto.index(MARCADOR_INICIO)
    fim = texto.index(MARCADOR_FIM, inicio) + len(MARCADOR_FIM)
    return texto[:inicio].rstrip() + BLOCO + texto[fim:].lstrip()


def main() -> None:
    pagina = encontrar_pagina()
    texto = pagina.read_text(encoding="utf-8")

    backup = pagina.with_suffix(".py.bak_ise_janela_v2")
    backup.write_text(texto, encoding="utf-8", newline="\n")

    atualizado = substituir_bloco(texto)
    pagina.write_text(atualizado, encoding="utf-8", newline="\n")

    print(f"Aba ISE por Janela V2 instalada em: {pagina}")
    print(f"Backup criado em: {backup}")


if __name__ == "__main__":
    main()

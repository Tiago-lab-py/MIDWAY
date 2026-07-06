from pathlib import Path


CONTEUDO_LIMPO = '''import streamlit as st
from dotenv import load_dotenv

from midway.web.ise_janela_component import mostrar_simulacao_ise_por_janela


load_dotenv()

st.title("Simulação ISE")
st.caption("Simulação por janelas específicas, com regional, período e cálculo sob demanda.")

mostrar_simulacao_ise_por_janela()
'''


def encontrar_pagina() -> Path:
    candidatos = [
        Path("midway") / "web" / "pages" / "04_Simulacao_ISE.py",
        Path("pages") / "04_Simulacao_ISE.py",
        Path("04_Simulacao_ISE.py"),
    ]
    for candidato in candidatos:
        if candidato.exists():
            return candidato
    raise FileNotFoundError(
        "Nao encontrei 04_Simulacao_ISE.py. Execute este script na raiz do projeto D:\\MIDWAY_novo."
    )


def main() -> None:
    pagina = encontrar_pagina()
    texto_atual = pagina.read_text(encoding="utf-8")

    backup = pagina.with_suffix(".py.bak_sem_duplicidade_ise")
    backup.write_text(texto_atual, encoding="utf-8", newline="\n")

    pagina.write_text(CONTEUDO_LIMPO, encoding="utf-8", newline="\n")

    print(f"Duplicidade removida em: {pagina}")
    print(f"Backup criado em: {backup}")
    print("Agora a pagina 04_Simulacao_ISE.py mostra apenas a Simulacao ISE dentro das abas.")


if __name__ == "__main__":
    main()

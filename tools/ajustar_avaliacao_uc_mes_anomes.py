from pathlib import Path


CAMINHO = Path("midway") / "web" / "library" / "avaliacao_uc.py"


def main() -> None:
    if not CAMINHO.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {CAMINHO}")

    texto = CAMINHO.read_text(encoding="utf-8")
    backup = CAMINHO.with_suffix(".py.bak_mes_anomes")
    backup.write_text(texto, encoding="utf-8", newline="\n")

    if "import os" not in texto:
        texto = texto.replace("from datetime import date\n", "import os\nfrom datetime import date\n")

    helper = '''

def _periodo_padrao_anomes() -> tuple[date, date]:
    anomes = os.getenv("ANOMES", "")
    if len(anomes) == 6 and anomes.isdigit():
        ano = int(anomes[:4])
        mes = int(anomes[4:6])
        inicio = date(ano, mes, 1)
        if mes == 12:
            fim = date(ano + 1, 1, 1) - pd.Timedelta(days=1)
        else:
            fim = date(ano, mes + 1, 1) - pd.Timedelta(days=1)
        return inicio, fim.date() if hasattr(fim, "date") else fim

    hoje = date.today()
    inicio = hoje.replace(day=1)
    return inicio, hoje
'''

    if "def _periodo_padrao_anomes" not in texto:
        texto = texto.replace("\ndef _fmt_sql_date", helper + "\n\ndef _fmt_sql_date", 1)

    antigo = '''    left, middle, right = st.columns([1, 1, 1])
    with left:
        uc = st.text_input("Número UC", value="", placeholder="Ex.: 116418249")
    with middle:
        start_date = st.date_input("Data inicial", value=date.today().replace(day=1))
    with right:
        end_date = st.date_input("Data final", value=date.today())
'''

    novo = '''    periodo_inicio_padrao, periodo_fim_padrao = _periodo_padrao_anomes()

    left, middle, right = st.columns([1, 1, 1])
    with left:
        uc = st.text_input("Número UC", value="", placeholder="Ex.: 116418249")
    with middle:
        start_date = st.date_input("Data inicial", value=periodo_inicio_padrao)
    with right:
        end_date = st.date_input("Data final", value=periodo_fim_padrao)
'''

    if antigo in texto:
        texto = texto.replace(antigo, novo, 1)
    elif "periodo_inicio_padrao, periodo_fim_padrao = _periodo_padrao_anomes()" not in texto:
        raise RuntimeError("Nao encontrei o bloco de datas para substituir.")

    CAMINHO.write_text(texto, encoding="utf-8", newline="\n")
    print(f"Ajustado: {CAMINHO}")
    print(f"Backup: {backup}")
    print("A Avaliacao UC agora usa ANOMES como periodo padrao.")


if __name__ == "__main__":
    main()

from pathlib import Path


CAMINHO = Path("midway") / "web" / "library" / "avaliacao_uc.py"


def inserir_campos_atributos(texto: str) -> str:
    if '"COD_GRUPO_NIVEL_TENSAO_UC",' in texto:
        return texto

    alvo = '''        "GRUPO_TENSAO",
        "TIPO_META",
'''
    novo = '''        "GRUPO_TENSAO",
        "COD_GRUPO_NIVEL_TENSAO_UC",
        "COD_NIVEL_TENSAO_UC",
        "TIPO_META",
'''
    if alvo not in texto:
        raise RuntimeError("Nao encontrei o bloco de atributos para inserir tensao.")
    return texto.replace(alvo, novo, 1)


def inserir_helpers_filtro(texto: str) -> str:
    if "def filter_options_consumidores" in texto:
        return texto

    helper = r'''

@st.cache_data(show_spinner=False)
def filter_options_consumidores(db_path: str, column_name: str):
    if not require_table(db_path, "gold_consumidores"):
        return []

    columns = _table_columns(db_path, "gold_consumidores")
    actual_column = _first_existing(columns, [column_name])
    if not actual_column:
        return []

    df = query_df(
        db_path,
        f"""
        SELECT DISTINCT NULLIF(TRIM(CAST("{actual_column}" AS VARCHAR)), '') AS VALOR
        FROM gold_consumidores
        WHERE NULLIF(TRIM(CAST("{actual_column}" AS VARCHAR)), '') IS NOT NULL
        ORDER BY VALOR
        """,
    )
    return df["VALOR"].astype(str).tolist()


def _sql_filter_consumidor(alias: str, column_name: str, values: list[str]) -> str:
    if not values:
        return ""
    escaped = ", ".join(sql_literal_for_streamlit(str(value)) for value in values)
    return f' AND NULLIF(TRIM(CAST({alias}."{column_name}" AS VARCHAR)), \'\') IN ({escaped})'
'''

    marcador = "\n@st.cache_data(show_spinner=False)\ndef uc_attributes"
    if marcador not in texto:
        raise RuntimeError("Nao encontrei local para inserir helpers de filtro.")
    return texto.replace(marcador, helper + marcador, 1)


def substituir_outlier_ranking(texto: str) -> str:
    antigo = '''@st.cache_data(show_spinner=False)
def outlier_uc_ranking(db_path: str, sample_limit: int):'''
    if antigo not in texto:
        return texto

    novo = '''@st.cache_data(show_spinner=False)
def outlier_uc_ranking(
    db_path: str,
    sample_limit: int,
    grupos_tensao: tuple[str, ...] = (),
    niveis_tensao: tuple[str, ...] = (),
):'''
    texto = texto.replace(antigo, novo, 1)

    if "grupo_filter_sql = _sql_filter_consumidor" not in texto:
        alvo = '''    valid_pos_expr = (
        "UPPER(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR)))"
        if _has_column(db_path, "gold_apuracao_uc", "VALID_POS_OPERACAO")
        else "'N'"
    )
'''
        novo_bloco = '''    valid_pos_expr = (
        "UPPER(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR)))"
        if _has_column(db_path, "gold_apuracao_uc", "VALID_POS_OPERACAO")
        else "'N'"
    )
    consumidores_cols = _table_columns(db_path, "gold_consumidores") if require_table(db_path, "gold_consumidores") else []
    uc_consumidor_col = _first_existing(consumidores_cols, ["UC", "NUM_UC", "NUM_UC_UCI", "ISN_UC", "NUM_UC_HCAI"])
    grupo_col = _first_existing(consumidores_cols, ["COD_GRUPO_NIVEL_TENSAO_UC"])
    nivel_col = _first_existing(consumidores_cols, ["COD_NIVEL_TENSAO_UC"])
    grupo_select = f'NULLIF(TRIM(CAST(g."{grupo_col}" AS VARCHAR)), \\'\\')' if grupo_col else "NULL"
    nivel_select = f'NULLIF(TRIM(CAST(g."{nivel_col}" AS VARCHAR)), \\'\\')' if nivel_col else "NULL"
    consumidor_join = (
        f'LEFT JOIN gold_consumidores g ON TRIM(CAST(g."{uc_consumidor_col}" AS VARCHAR)) = e.UC'
        if uc_consumidor_col
        else ""
    )
    grupo_filter_sql = _sql_filter_consumidor("g", grupo_col, list(grupos_tensao)) if grupo_col else ""
    nivel_filter_sql = _sql_filter_consumidor("g", nivel_col, list(niveis_tensao)) if nivel_col else ""
'''
        if alvo not in texto:
            raise RuntimeError("Nao encontrei bloco valid_pos_expr em outlier_uc_ranking.")
        texto = texto.replace(alvo, novo_bloco, 1)

    if "grupo_select AS COD_GRUPO_NIVEL_TENSAO_UC" not in texto:
        alvo = '''                e.*,
                c.META_DIC,
'''
        novo_bloco = '''                e.*,
                {grupo_select} AS COD_GRUPO_NIVEL_TENSAO_UC,
                {nivel_select} AS COD_NIVEL_TENSAO_UC,
                c.META_DIC,
'''
        texto = texto.replace(alvo, novo_bloco, 1)

    if "{consumidor_join}" not in texto:
        alvo = '''            FROM eventos_uc e
            LEFT JOIN continuidade c
              ON c.UC = e.UC
'''
        novo_bloco = '''            FROM eventos_uc e
            LEFT JOIN continuidade c
              ON c.UC = e.UC
            {consumidor_join}
            WHERE 1 = 1
              {grupo_filter_sql}
              {nivel_filter_sql}
'''
        if alvo not in texto:
            raise RuntimeError("Nao encontrei join da CTE score para inserir consumidores.")
        texto = texto.replace(alvo, novo_bloco, 1)

    return texto


def inserir_filtros_ui(texto: str) -> str:
    if "grupo_filter = st.multiselect" in texto:
        return texto

    alvo = '''    col_score, col_faixa, col_pos = st.columns([1, 1, 1])
    with col_score:
        min_score = st.slider("Score mínimo pendente", 0, 100, 0, step=5)
    with col_faixa:
        faixa = st.selectbox("Faixa pendente", ["Todas", "Baixo", "Médio", "Alto", "Crítico"])
    with col_pos:
        filtro_pos = st.selectbox(
            "Validação Pós-Operação",
            ["Pendentes", "Todos", "Somente validados", "Parcialmente validados"],
        )

    ranking_df = outlier_uc_ranking(db_path, sample_limit * 5)
'''

    novo = '''    col_score, col_faixa, col_pos = st.columns([1, 1, 1])
    with col_score:
        min_score = st.slider("Score mínimo pendente", 0, 100, 0, step=5)
    with col_faixa:
        faixa = st.selectbox("Faixa pendente", ["Todas", "Baixo", "Médio", "Alto", "Crítico"])
    with col_pos:
        filtro_pos = st.selectbox(
            "Validação Pós-Operação",
            ["Pendentes", "Todos", "Somente validados", "Parcialmente validados"],
        )

    grupo_options = filter_options_consumidores(db_path, "COD_GRUPO_NIVEL_TENSAO_UC")
    nivel_options = filter_options_consumidores(db_path, "COD_NIVEL_TENSAO_UC")
    col_grupo, col_nivel = st.columns([1, 1])
    with col_grupo:
        grupo_filter = st.multiselect("Grupo nível tensão UC", grupo_options)
    with col_nivel:
        nivel_filter = st.multiselect("Nível tensão UC", nivel_options)

    ranking_df = outlier_uc_ranking(
        db_path,
        sample_limit * 5,
        tuple(grupo_filter),
        tuple(nivel_filter),
    )
'''

    if alvo not in texto:
        raise RuntimeError("Nao encontrei bloco de filtros do Outlier UC.")
    return texto.replace(alvo, novo, 1)


def main() -> None:
    if not CAMINHO.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {CAMINHO}")

    texto = CAMINHO.read_text(encoding="utf-8")
    backup = CAMINHO.with_suffix(".py.bak_tensao_uc")
    backup.write_text(texto, encoding="utf-8", newline="\n")

    texto = inserir_campos_atributos(texto)
    texto = inserir_helpers_filtro(texto)
    texto = substituir_outlier_ranking(texto)
    texto = inserir_filtros_ui(texto)

    CAMINHO.write_text(texto, encoding="utf-8", newline="\n")
    print(f"Atualizado: {CAMINHO}")
    print(f"Backup: {backup}")
    print("Incluidos COD_GRUPO_NIVEL_TENSAO_UC, COD_NIVEL_TENSAO_UC e filtros no Outlier UC.")


if __name__ == "__main__":
    main()

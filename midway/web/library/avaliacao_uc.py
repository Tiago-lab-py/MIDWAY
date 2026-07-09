from __future__ import annotations

import calendar
import os
from datetime import date

from midway.web.library.shared import *


def _table_columns(db_path: str, table_name: str) -> list[str]:
    return query_df(
        db_path,
        f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'main'
          AND table_name = {sql_literal_for_streamlit(table_name)}
        ORDER BY ordinal_position
        """,
    )["column_name"].tolist()


def _has_column(db_path: str, table_name: str, column_name: str) -> bool:
    if not require_table(db_path, table_name):
        return False
    return column_name.upper() in {col.upper() for col in _table_columns(db_path, table_name)}


def _first_existing(columns: list[str], candidates: list[str]) -> str | None:
    mapping = {col.upper(): col for col in columns}
    for candidate in candidates:
        if candidate.upper() in mapping:
            return mapping[candidate.upper()]
    return None


def _fmt_sql_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _anomes_periodo() -> tuple[date, date]:
    anomes = os.getenv("ANOMES", "202606")
    ano = int(anomes[:4])
    mes = int(anomes[4:6])
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, 1), date(ano, mes, ultimo_dia)


def _tabela_tensao_uc(db_path: str) -> str | None:
    for table_name in ["gold_consumidores", "silver_iqs_vrc", "gold_vrc"]:
        if not require_table(db_path, table_name):
            continue

        columns = _table_columns(db_path, table_name)
        grupo_col = _first_existing(
            columns,
            [
                "COD_GRUPO_NIVEL_TENSAO_UC",
                "COD_GRUPO_NIVEL_TENSAO",
                "GRUPO_NIVEL_TENSAO_UC",
                "GRUPO_NIVEL_TENSAO",
                "GRUPO_TENSAO",
                "COD_GRUPO_TENSAO",
            ],
        )
        nivel_col = _first_existing(
            columns,
            [
                "COD_NIVEL_TENSAO_UC",
                "COD_NIVEL_TENSAO",
                "NIVEL_TENSAO_UC",
                "NIVEL_TENSAO",
            ],
        )

        if grupo_col or nivel_col:
            return table_name

    return None


def _coluna_tensao_uc(db_path: str, tipo: str) -> tuple[str | None, str | None]:
    table_name = _tabela_tensao_uc(db_path)
    if not table_name:
        return None, None

    columns = _table_columns(db_path, table_name)

    if tipo == "grupo":
        return table_name, _first_existing(
            columns,
            [
                "COD_GRUPO_NIVEL_TENSAO_UC",
                "COD_GRUPO_NIVEL_TENSAO",
                "GRUPO_NIVEL_TENSAO_UC",
                "GRUPO_NIVEL_TENSAO",
                "GRUPO_TENSAO",
                "COD_GRUPO_TENSAO",
            ],
        )

    if tipo == "nivel":
        return table_name, _first_existing(
            columns,
            [
                "COD_NIVEL_TENSAO_UC",
                "COD_NIVEL_TENSAO",
                "NIVEL_TENSAO_UC",
                "NIVEL_TENSAO",
            ],
        )

    return table_name, None


def _uc_col_tensao(db_path: str, table_name: str | None) -> str | None:
    if not table_name:
        return None

    columns = _table_columns(db_path, table_name)
    return _first_existing(
        columns,
        [
            "UC",
            "NUM_UC",
            "NUM_UC_UCI",
            "ISN_UC",
            "NUM_UC_HCAI",
        ],
    )


@st.cache_data(show_spinner=False)
def filter_options_consumidores(db_path: str, tipo: str):
    if require_table(db_path, "gold_outlier_uc"):
        column_name = (
            "COD_GRUPO_NIVEL_TENSAO_UC"
            if tipo == "grupo"
            else "COD_NIVEL_TENSAO_UC"
        )

        df = query_df(
            db_path,
            f"""
            SELECT DISTINCT
                NULLIF(TRIM(CAST({column_name} AS VARCHAR)), '') AS VALOR
            FROM gold_outlier_uc
            WHERE NULLIF(TRIM(CAST({column_name} AS VARCHAR)), '') IS NOT NULL
            ORDER BY VALOR
            """,
        )

        if not df.empty:
            return df["VALOR"].astype(str).tolist()

    table_name, actual_column = _coluna_tensao_uc(db_path, tipo)
    if not table_name or not actual_column:
        return []

    df = query_df(
        db_path,
        f"""
        SELECT DISTINCT
            NULLIF(TRIM(CAST("{actual_column}" AS VARCHAR)), '') AS VALOR
        FROM {table_name}
        WHERE NULLIF(TRIM(CAST("{actual_column}" AS VARCHAR)), '') IS NOT NULL
        ORDER BY VALOR
        """,
    )

    if df.empty:
        return []

    return df["VALOR"].astype(str).tolist()


def _sql_filter_consumidor(alias: str, column_name: str | None, values: list[str]) -> str:
    if not column_name or not values:
        return ""
    escaped = ", ".join(sql_literal_for_streamlit(str(value)) for value in values)
    return f' AND NULLIF(TRIM(CAST({alias}."{column_name}" AS VARCHAR)), \'\') IN ({escaped})'


@st.cache_data(show_spinner=False)
def uc_attributes(db_path: str, uc: str):
    if not require_table(db_path, "gold_consumidores"):
        return pd.DataFrame()

    columns = _table_columns(db_path, "gold_consumidores")
    uc_col = _first_existing(columns, ["UC", "NUM_UC", "NUM_UC_UCI", "ISN_UC", "NUM_UC_HCAI"])
    if not uc_col:
        return pd.DataFrame()

    selected_cols = []
    for col in [
        uc_col,
        "NUM_UC_ANEEL",
        "NOME_CLIENTE",
        "NOM_CLIENTE",
        "ENDERECO",
        "DSC_ENDERECO",
        "SITUACAO",
        "CLASSE",
        "AREA",
        "GRUPO_TENSAO",
        "COD_GRUPO_NIVEL_TENSAO_UC",
        "COD_GRUPO_NIVEL_TENSAO",
        "COD_NIVEL_TENSAO_UC",
        "COD_NIVEL_TENSAO",
        "TIPO_META",
        "SISTEMA",
        "POSTO",
        "CONJUNTO",
        "ALIMENTADOR_ELETRICO",
        "ALIMENTADOR_OPERACIONAL",
    ]:
        if col and col.upper() in {c.upper() for c in columns}:
            selected_cols.append(col)

    if not selected_cols:
        selected_cols = [uc_col]

    select_sql = ", ".join(f'"{col}"' for col in dict.fromkeys(selected_cols))
    return query_df(
        db_path,
        f"""
        SELECT {select_sql}
        FROM gold_consumidores
        WHERE TRIM(CAST("{uc_col}" AS VARCHAR)) = {sql_literal_for_streamlit(str(uc).strip())}
        LIMIT 1
        """,
    )


@st.cache_data(show_spinner=False)
def uc_interruptions(db_path: str, uc: str, start_date: date, end_date: date):
    return query_df(
        db_path,
        f"""
        SELECT
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP AS INTERRUPCAO,
            NUM_INTRP_UCI,
            DTHR_INICIO_INTRP_UC AS DATA_HORA_INICIO,
            DATA_HORA_FIM_INTRP AS DATA_HORA_FIM,
            DURACAO_HORA AS DURACAO,
            CASE WHEN COALESCE(CI_LIQUIDO, 0) > 0 THEN 'S' ELSE 'NÃO' END AS FIC,
            CASE WHEN COALESCE(CHI_LIQUIDO, 0) > 0 THEN 'S' ELSE 'NÃO' END AS DIC,
            CASE WHEN COALESCE(CHI_LIQUIDO, 0) > 0 THEN 'S' ELSE 'NÃO' END AS DMIC,
            CASE WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL THEN 'S' ELSE '' END AS MANOBRA,
            TIPO_PROTOC_JUSTIF_UCI AS TIPO_PROTOCOLO,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_TIPO_INTRP,
            CI_BRUTO,
            CHI_BRUTO,
            CI_LIQUIDO,
            CHI_LIQUIDO,
            INTERRUPCAO_LONGA,
            INTERRUPCAO_CONTABILIZAVEL
        FROM gold_apuracao_uc
        WHERE TRIM(CAST(NUM_UC_UCI AS VARCHAR)) = {sql_literal_for_streamlit(str(uc).strip())}
          AND CAST(DTHR_INICIO_INTRP_UC AS DATE) >= DATE '{_fmt_sql_date(start_date)}'
          AND CAST(DTHR_INICIO_INTRP_UC AS DATE) <= DATE '{_fmt_sql_date(end_date)}'
        ORDER BY DTHR_INICIO_INTRP_UC, NUM_SEQ_INTRP, NUM_INTRP_UCI
        """,
    )


@st.cache_data(show_spinner=False)
def uc_continuity(db_path: str, uc: str):
    if not require_table(db_path, "gold_continuidade_uc"):
        return pd.DataFrame()

    return query_df(
        db_path,
        f"""
        SELECT *
        FROM gold_continuidade_uc
        WHERE TRIM(CAST(UC AS VARCHAR)) = {sql_literal_for_streamlit(str(uc).strip())}
        LIMIT 1
        """,
    )


@st.cache_data(show_spinner=False)
def uc_ressarcimento(db_path: str, uc: str):
    if not require_table(db_path, "gold_ressarcimento_prodist"):
        return pd.DataFrame()

    return query_df(
        db_path,
        f"""
        SELECT *
        FROM gold_ressarcimento_prodist
        WHERE TRIM(CAST(UC AS VARCHAR)) = {sql_literal_for_streamlit(str(uc).strip())}
        LIMIT 1
        """,
    )


def _metric_value(df, column: str, default=0):
    if df.empty or column not in df.columns:
        return default
    value = df.iloc[0][column]
    return default if pd.isna(value) else value


def _render_attributes(attributes_df, uc: str):
    st.markdown("### Atributos atuais da unidade consumidora")
    if attributes_df.empty:
        st.info("Atributos cadastrais não encontrados em `gold_consumidores` para esta UC.")
        st.write({"Número UC": uc})
        return

    row = attributes_df.iloc[0].to_dict()
    items = [(key, value) for key, value in row.items() if pd.notna(value)]
    left, right = st.columns(2)
    for idx, (key, value) in enumerate(items):
        target = left if idx % 2 == 0 else right
        target.markdown(f"**{key}**  \n{value}")


def _render_interruptions(interruptions_df, sample_limit: int):
    st.markdown("### Interrupções")
    if interruptions_df.empty:
        st.success("Nenhuma interrupção encontrada para os filtros informados.")
        return

    display_cols = [
        "DATA_HORA_INICIO",
        "DURACAO",
        "DIC",
        "FIC",
        "DMIC",
        "INTERRUPCAO",
        "TIPO_PROTOCOLO",
        "MANOBRA",
        "COD_CAUSA_INTRP",
        "COD_COMP_INTRP",
        "NUM_OCORRENCIA_ADMS",
    ]
    display_cols = [col for col in display_cols if col in interruptions_df.columns]
    st.dataframe(
        interruptions_df[display_cols].head(sample_limit),
        use_container_width=True,
        hide_index=True,
        column_config={
            "DURACAO": st.column_config.NumberColumn("Duração", format="%.3f"),
            "DATA_HORA_INICIO": st.column_config.DatetimeColumn("Data/hora início"),
        },
    )
    st.caption(f"{len(interruptions_df):,} registro(s) encontrado(s).")


def _render_indicators(continuity_df, ressarcimento_df):
    st.markdown("### Indicadores e ressarcimento")
    if continuity_df.empty and ressarcimento_df.empty:
        st.info("Indicadores não encontrados para esta UC.")
        return

    cards = [
        ("DIC", _metric_value(continuity_df, "DIC"), "Líquido"),
        ("FIC", _metric_value(continuity_df, "FIC"), "Líquido"),
        ("DMIC", _metric_value(continuity_df, "DMIC"), "Máxima duração"),
        ("DIC_BRT", _metric_value(continuity_df, "DIC_BRT"), "Bruto"),
        ("FIC_BRT", _metric_value(continuity_df, "FIC_BRT"), "Bruto"),
        ("Comp. PRODIST", _metric_value(ressarcimento_df, "COMP_TOTAL_PRODIST"), "Total UC"),
    ]
    show_metric_cards(cards)

    detail_frames = []
    if not continuity_df.empty:
        detail_frames.append(("Continuidade", continuity_df))
    if not ressarcimento_df.empty:
        detail_frames.append(("Ressarcimento PRODIST", ressarcimento_df))

    for title, df in detail_frames:
        with st.expander(title, expanded=False):
            st.dataframe(df, use_container_width=True, hide_index=True)


def show_consulta_uc(db_path: str, sample_limit: int) -> None:
    st.subheader("Avaliação de UC")
    st.caption(
        "Consulta operacional por unidade consumidora, reunindo atributos, interrupções, "
        "indicadores de continuidade e ressarcimento estimado."
    )

    if not require_table(db_path, "gold_apuracao_uc"):
        st.info("Execute `run.bat apuracao_parcial` para gerar a base de avaliação.")
        return

    periodo_inicio, periodo_fim = _anomes_periodo()

    left, middle, right = st.columns([1, 1, 1])
    with left:
        uc = st.text_input("Número UC", value="", placeholder="Ex.: 116418249")
    with middle:
        start_date = st.date_input("Data inicial", value=periodo_inicio)
    with right:
        end_date = st.date_input("Data final", value=periodo_fim)

    opt_left, opt_middle, opt_right = st.columns([1, 1, 1])
    with opt_left:
        show_interruptions = st.checkbox("Mostrar interrupções", value=True)
    with opt_middle:
        show_indicators = st.checkbox("Mostrar indicadores", value=True)
    with opt_right:
        show_raw_detail = st.checkbox("Mostrar detalhe completo", value=False)

    pesquisar = st.button("Pesquisar", type="primary")
    if not pesquisar:
        st.info("Informe a UC e clique em Pesquisar.")
        return

    if not uc.strip():
        st.warning("Informe o número da UC.")
        return

    attributes_df = uc_attributes(db_path, uc)
    interruptions_df = uc_interruptions(db_path, uc, start_date, end_date)
    continuity_df = uc_continuity(db_path, uc)
    ressarcimento_df = uc_ressarcimento(db_path, uc)

    show_metric_cards(
        [
            ("Interrupções", len(interruptions_df), "No período"),
            ("DIC período", interruptions_df["CHI_LIQUIDO"].sum() if "CHI_LIQUIDO" in interruptions_df else 0, "Soma líquida"),
            ("FIC período", interruptions_df["CI_LIQUIDO"].sum() if "CI_LIQUIDO" in interruptions_df else 0, "Soma líquida"),
            ("Comp. PRODIST", _metric_value(ressarcimento_df, "COMP_TOTAL_PRODIST"), "Total UC"),
        ]
    )

    _render_attributes(attributes_df, uc)

    if show_interruptions:
        _render_interruptions(interruptions_df, sample_limit)

    if show_indicators:
        _render_indicators(continuity_df, ressarcimento_df)

    if show_raw_detail:
        with st.expander("Dados brutos da consulta", expanded=False):
            st.markdown("#### Interrupções completas")
            st.dataframe(interruptions_df, use_container_width=True, hide_index=True)


@st.cache_data(show_spinner=False)
def outlier_uc_ranking(
    db_path: str,
    sample_limit: int,
    grupos_tensao: tuple[str, ...] = (),
    niveis_tensao: tuple[str, ...] = (),
):
    filtros = ""

    if grupos_tensao:
        valores = ", ".join(sql_literal_for_streamlit(str(value)) for value in grupos_tensao)
        filtros += f"""
          AND NULLIF(TRIM(CAST(COD_GRUPO_NIVEL_TENSAO_UC AS VARCHAR)), '') IN ({valores})
        """

    if niveis_tensao:
        valores = ", ".join(sql_literal_for_streamlit(str(value)) for value in niveis_tensao)
        filtros += f"""
          AND NULLIF(TRIM(CAST(COD_NIVEL_TENSAO_UC AS VARCHAR)), '') IN ({valores})
        """

    return query_df(
        db_path,
        f"""
        SELECT *
        FROM gold_outlier_uc
        WHERE 1 = 1
          {filtros}
        ORDER BY
            SCORE_OUTLIER_UC_PENDENTE DESC,
            COMP_TOTAL_PRODIST_PENDENTE_POS DESC,
            DIC_PENDENTE_POS DESC,
            FIC_PENDENTE_POS DESC
        LIMIT {int(sample_limit)}
        """,
    )


def show_outlier_uc(db_path: str, sample_limit: int) -> None:
    st.subheader("Outlier UC")
    st.caption(
        "Ranking exploratório para localizar UCs com comportamento atípico em continuidade, "
        "protocolo, duração e compensação. Ocorrências com VALID_POS_OPERACAO = S deixam de pesar como pendência."
    )

    required_tables = ["gold_outlier_uc"]
    if not all(require_table(db_path, table_name) for table_name in required_tables):
        return

    col_score, col_faixa, col_pos = st.columns([1, 1, 1])
    with col_score:
        min_score = st.slider("Score mínimo pendente", 0, 100, 0, step=5)
    with col_faixa:
        faixa = st.selectbox("Faixa pendente", ["Todas", "Baixo", "Médio", "Alto", "Crítico"])
    with col_pos:
        filtro_pos = st.selectbox(
            "Validação Pós-Operação",
            ["Pendentes", "Todos", "Somente validados", "Parcialmente validados"],
        )

    grupo_options = filter_options_consumidores(db_path, "grupo")
    nivel_options = filter_options_consumidores(db_path, "nivel")
    tensao_table = _tabela_tensao_uc(db_path)

    col_grupo, col_nivel = st.columns([1, 1])
    with col_grupo:
        grupo_filter = st.multiselect("Grupo nível tensão UC", grupo_options)
    with col_nivel:
        nivel_filter = st.multiselect("Nível tensão UC", nivel_options)

    if tensao_table:
        st.caption(f"Filtros de tensão carregados de `{tensao_table}`.")
    else:
        st.warning(
            "Não encontrei colunas de grupo/nível de tensão em `gold_consumidores`, "
            "`silver_iqs_vrc` ou `gold_vrc`."
        )

    ranking_df = outlier_uc_ranking(
        db_path,
        sample_limit * 5,
        tuple(grupo_filter),
        tuple(nivel_filter),
    )
    if ranking_df.empty:
        st.info("Execute `run.bat apuracao_parcial` para gerar `gold_outlier_uc`.")
        return

    ranking_df = ranking_df[ranking_df["SCORE_OUTLIER_UC_PENDENTE"] >= min_score]
    if faixa != "Todas":
        ranking_df = ranking_df[ranking_df["FAIXA_OUTLIER_PENDENTE"] == faixa]

    if filtro_pos == "Pendentes":
        ranking_df = ranking_df[ranking_df["QTD_OCORRENCIAS_PENDENTES_POS"] > 0]
    elif filtro_pos == "Somente validados":
        ranking_df = ranking_df[ranking_df["QTD_OCORRENCIAS_PENDENTES_POS"] == 0]
    elif filtro_pos == "Parcialmente validados":
        ranking_df = ranking_df[ranking_df["STATUS_POS_OPERACAO"] == "Parcialmente validado"]

    ranking_df = ranking_df.head(sample_limit)

    if ranking_df.empty:
        st.success("Nenhum outlier UC encontrado para os filtros informados.")
        return

    show_metric_cards(
        [
            ("UCs exibidas", len(ranking_df), "Após filtros"),
            ("Pendências pós", ranking_df["QTD_OCORRENCIAS_PENDENTES_POS"].sum(), "Ocorrências não validadas"),
            ("Validadas pós", ranking_df["QTD_OCORRENCIAS_VALIDADAS_POS"].sum(), "Ocorrências já aceitas"),
            ("Comp. pendente", ranking_df["COMP_TOTAL_PRODIST_PENDENTE_POS"].sum(), "Estimativa do ranking"),
        ]
    )

    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SCORE_OUTLIER_UC_PENDENTE": st.column_config.ProgressColumn(
                "Score pendente",
                min_value=0,
                max_value=100,
            ),
            "SCORE_OUTLIER_UC": st.column_config.ProgressColumn(
                "Score total",
                min_value=0,
                max_value=100,
            ),
            "STATUS_POS_OPERACAO": st.column_config.TextColumn("Status pós"),
            "QTD_OCORRENCIAS_PENDENTES_POS": st.column_config.NumberColumn("Pendentes pós", format="%d"),
            "QTD_OCORRENCIAS_VALIDADAS_POS": st.column_config.NumberColumn("Validadas pós", format="%d"),
            "PCT_META_DIC_PENDENTE_POS": st.column_config.NumberColumn("% META DIC pend.", format="%.2f%%"),
            "PCT_META_FIC_PENDENTE_POS": st.column_config.NumberColumn("% META FIC pend.", format="%.2f%%"),
            "PCT_META_DMIC_PENDENTE_POS": st.column_config.NumberColumn("% META DMIC pend.", format="%.2f%%"),
            "COMP_TOTAL_PRODIST_PENDENTE_POS": st.column_config.NumberColumn("COMP pendente", format="%.2f"),
            "COMP_TOTAL_PRODIST": st.column_config.NumberColumn("COMP total", format="%.2f"),
            "DIC_PENDENTE_POS": st.column_config.NumberColumn("DIC pend.", format="%.3f"),
            "FIC_PENDENTE_POS": st.column_config.NumberColumn("FIC pend.", format="%.0f"),
            "DMIC_PENDENTE_POS": st.column_config.NumberColumn("DMIC pend.", format="%.3f"),
        },
    )

    st.download_button(
        "Baixar Outlier UC",
        ranking_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="outlier_uc.csv",
        mime="text/csv",
    )


def show_avaliacao_uc(db_path: str, sample_limit: int) -> None:
    tabs = st.tabs(["Outlier UC", "Consulta UC"])
    with tabs[0]:
        show_outlier_uc(db_path, sample_limit)
    with tabs[1]:
        show_consulta_uc(db_path, sample_limit)
from pathlib import Path


CAMINHO = Path("midway") / "web" / "library" / "avaliacao_uc.py"

FUNCOES_OUTLIER = r'''

@st.cache_data(show_spinner=False)
def outlier_uc_ranking(db_path: str, sample_limit: int):
    return query_df(
        db_path,
        f"""
        WITH eventos_uc AS (
            SELECT
                TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS UC,
                ANY_VALUE(REGIONAL) AS REGIONAL,
                ANY_VALUE(COD_CONJTO_ELET_ANEEL_INTRP) AS CONJUNTO,
                COUNT(*) AS QTD_INTERRUPCOES,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS FIC,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS DIC,
                MAX(COALESCE(CHI_LIQUIDO, 0)) AS DMIC,
                SUM(CASE WHEN COALESCE(DURACAO_HORA, 0) >= 24 THEN 1 ELSE 0 END) AS QTD_DURACAO_GE_24H,
                SUM(CASE WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL THEN 1 ELSE 0 END) AS QTD_MANOBRA,
                COUNT(DISTINCT TIPO_PROTOC_JUSTIF_UCI) AS QTD_TIPOS_PROTOCOLO,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS CHI_TIPO_0,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) <> '0' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS CHI_TIPO_NAO_0
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            GROUP BY TRIM(CAST(NUM_UC_UCI AS VARCHAR))
        ),
        continuidade AS (
            SELECT
                TRIM(CAST(UC AS VARCHAR)) AS UC,
                COALESCE(META_DIC, 0) AS META_DIC,
                COALESCE(META_FIC, 0) AS META_FIC,
                COALESCE(META_DMIC, 0) AS META_DMIC,
                COALESCE(COMP_TOTAL_PRODIST, 0) AS COMP_TOTAL_PRODIST
            FROM gold_ressarcimento_prodist
        ),
        score AS (
            SELECT
                e.*,
                c.META_DIC,
                c.META_FIC,
                c.META_DMIC,
                c.COMP_TOTAL_PRODIST,
                CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC / c.META_DIC * 100 ELSE 0 END AS PCT_META_DIC,
                CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC / c.META_FIC * 100 ELSE 0 END AS PCT_META_FIC,
                CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC / c.META_DMIC * 100 ELSE 0 END AS PCT_META_DMIC,
                (
                    LEAST(CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC / c.META_DIC * 30 ELSE 0 END, 30)
                  + LEAST(CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC / c.META_FIC * 20 ELSE 0 END, 20)
                  + LEAST(CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC / c.META_DMIC * 20 ELSE 0 END, 20)
                  + LEAST(e.QTD_DURACAO_GE_24H * 10, 10)
                  + LEAST(e.QTD_TIPOS_PROTOCOLO * 5, 10)
                  + LEAST(COALESCE(c.COMP_TOTAL_PRODIST, 0) / 10000.0, 10)
                ) AS SCORE_OUTLIER_UC
            FROM eventos_uc e
            LEFT JOIN continuidade c
              ON c.UC = e.UC
        )
        SELECT
            *,
            CASE
                WHEN SCORE_OUTLIER_UC >= 80 THEN 'Crítico'
                WHEN SCORE_OUTLIER_UC >= 60 THEN 'Alto'
                WHEN SCORE_OUTLIER_UC >= 40 THEN 'Médio'
                ELSE 'Baixo'
            END AS FAIXA_OUTLIER
        FROM score
        ORDER BY
            SCORE_OUTLIER_UC DESC,
            COMP_TOTAL_PRODIST DESC,
            DIC DESC,
            FIC DESC
        LIMIT {int(sample_limit)}
        """,
    )


def show_outlier_uc(db_path: str, sample_limit: int) -> None:
    st.subheader("Outlier UC")
    st.caption(
        "Ranking exploratório para localizar UCs com comportamento atípico em continuidade, "
        "protocolo, duração e compensação."
    )

    required_tables = ["gold_apuracao_uc", "gold_ressarcimento_prodist"]
    if not all(require_table(db_path, table_name) for table_name in required_tables):
        return

    col_score, col_faixa = st.columns([1, 1])
    with col_score:
        min_score = st.slider("Score mínimo outlier", 0, 100, 0, step=5)
    with col_faixa:
        faixa = st.selectbox("Faixa", ["Todas", "Baixo", "Médio", "Alto", "Crítico"])

    ranking_df = outlier_uc_ranking(db_path, sample_limit * 5)
    if ranking_df.empty:
        st.success("Nenhum outlier UC encontrado.")
        return

    ranking_df = ranking_df[ranking_df["SCORE_OUTLIER_UC"] >= min_score]
    if faixa != "Todas":
        ranking_df = ranking_df[ranking_df["FAIXA_OUTLIER"] == faixa]
    ranking_df = ranking_df.head(sample_limit)

    if ranking_df.empty:
        st.success("Nenhum outlier UC encontrado para os filtros informados.")
        return

    show_metric_cards(
        [
            ("UCs exibidas", len(ranking_df), "Após filtros"),
            ("Comp. PRODIST", ranking_df["COMP_TOTAL_PRODIST"].sum(), "Soma do ranking"),
            ("DIC", ranking_df["DIC"].sum(), "Soma líquida"),
            ("FIC", ranking_df["FIC"].sum(), "Soma líquida"),
        ]
    )

    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SCORE_OUTLIER_UC": st.column_config.ProgressColumn(
                "Score",
                min_value=0,
                max_value=100,
            ),
            "PCT_META_DIC": st.column_config.NumberColumn("% META DIC", format="%.2f%%"),
            "PCT_META_FIC": st.column_config.NumberColumn("% META FIC", format="%.2f%%"),
            "PCT_META_DMIC": st.column_config.NumberColumn("% META DMIC", format="%.2f%%"),
            "COMP_TOTAL_PRODIST": st.column_config.NumberColumn("COMP_TOTAL_PRODIST", format="%.2f"),
            "DIC": st.column_config.NumberColumn("DIC", format="%.3f"),
            "FIC": st.column_config.NumberColumn("FIC", format="%.0f"),
            "DMIC": st.column_config.NumberColumn("DMIC", format="%.3f"),
        },
    )

    st.download_button(
        "Baixar Outlier UC",
        ranking_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="outlier_uc.csv",
        mime="text/csv",
    )
'''


def main() -> None:
    if not CAMINHO.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {CAMINHO}")

    texto = CAMINHO.read_text(encoding="utf-8")
    backup = CAMINHO.with_suffix(".py.bak_outlier_uc")
    backup.write_text(texto, encoding="utf-8", newline="\n")

    if "def show_outlier_uc" not in texto:
        texto = texto.rstrip() + FUNCOES_OUTLIER

    antigo = '''    _render_attributes(attributes_df, uc)

    if show_interruptions:
        _render_interruptions(interruptions_df, sample_limit)

    if show_indicators:
        _render_indicators(continuity_df, ressarcimento_df)

    if show_raw_detail:
        with st.expander("Dados brutos da consulta", expanded=False):
            st.markdown("#### Interrupções completas")
            st.dataframe(interruptions_df, use_container_width=True, hide_index=True)
'''

    novo = '''    _render_attributes(attributes_df, uc)

    if show_interruptions:
        _render_interruptions(interruptions_df, sample_limit)

    if show_indicators:
        _render_indicators(continuity_df, ressarcimento_df)

    if show_raw_detail:
        with st.expander("Dados brutos da consulta", expanded=False):
            st.markdown("#### Interrupções completas")
            st.dataframe(interruptions_df, use_container_width=True, hide_index=True)
'''

    if "tabs = st.tabs([\"Outlier UC\", \"Consulta UC\"])" not in texto:
        texto = texto.replace(
            "def show_avaliacao_uc(db_path: str, sample_limit: int) -> None:",
            "def show_consulta_uc(db_path: str, sample_limit: int) -> None:",
            1,
        )
        texto = texto.replace(antigo, novo, 1)
        texto += '''


def show_avaliacao_uc(db_path: str, sample_limit: int) -> None:
    tabs = st.tabs(["Outlier UC", "Consulta UC"])
    with tabs[0]:
        show_outlier_uc(db_path, sample_limit)
    with tabs[1]:
        show_consulta_uc(db_path, sample_limit)
'''

    CAMINHO.write_text(texto, encoding="utf-8", newline="\n")
    print(f"Atualizado: {CAMINHO}")
    print(f"Backup: {backup}")
    print("Avaliacao UC agora possui abas: Outlier UC e Consulta UC.")


if __name__ == "__main__":
    main()

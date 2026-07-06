from __future__ import annotations

from midway.web.library.shared import *


def show_conjunto_diario(db_path: str, sample_limit: int) -> None:
    st.subheader("Impacto Diário por Conjunto")
    st.caption(
        "Ranking de ocorrências por dia e conjunto elétrico, medindo quanto cada ocorrência "
        "consome da meta DEC/FEC do conjunto."
    )

    if not require_table(db_path, "gold_impacto_conjunto_dia"):
        st.info("Execute `run.bat apuracao_parcial` para gerar `gold_impacto_conjunto_dia`.")
        return

    dates_df = query_df(
        db_path,
        """
        SELECT DISTINCT CAST(DATA_OCORRENCIA AS VARCHAR) AS DATA_OCORRENCIA
        FROM gold_impacto_conjunto_dia
        WHERE DATA_OCORRENCIA IS NOT NULL
        ORDER BY DATA_OCORRENCIA DESC
        """,
    )
    if dates_df.empty:
        st.info("Nenhum dado diário por conjunto encontrado.")
        return

    conjuntos_df = query_df(
        db_path,
        """
        SELECT DISTINCT COD_CONJUNTO_ANEEL
        FROM gold_impacto_conjunto_dia
        WHERE NULLIF(TRIM(CAST(COD_CONJUNTO_ANEEL AS VARCHAR)), '') IS NOT NULL
        ORDER BY COD_CONJUNTO_ANEEL
        """,
    )

    left, middle, right = st.columns([1, 1, 1])
    with left:
        selected_date = st.selectbox("Dia", dates_df["DATA_OCORRENCIA"].tolist())
    with middle:
        conjunto_options = ["Todos"] + conjuntos_df["COD_CONJUNTO_ANEEL"].astype(str).tolist()
        selected_conjunto = st.selectbox("Conjunto", conjunto_options)
    with right:
        min_pct = st.slider(
            "% mínimo da meta consumida",
            0.0,
            100.0,
            0.0,
            step=0.5,
            help="Filtro pelo maior percentual entre DEC e FEC consumido pela ocorrência.",
        )

    date_filter_sql = f"CAST(DATA_OCORRENCIA AS VARCHAR) = {sql_literal_for_streamlit(selected_date)}"
    conjunto_filter_sql = ""
    if selected_conjunto != "Todos":
        conjunto_filter_sql = (
            " AND CAST(COD_CONJUNTO_ANEEL AS VARCHAR) = "
            f"{sql_literal_for_streamlit(selected_conjunto)}"
        )

    summary_sql = f"""
        SELECT
            COUNT(*) AS OCORRENCIAS,
            COUNT(DISTINCT COD_CONJUNTO_ANEEL) AS CONJUNTOS,
            SUM(QTD_UCS_AFETADAS) AS UCS_AFETADAS_SOMA,
            SUM(DIC_IMPACTO) AS DIC_IMPACTO,
            SUM(FIC_IMPACTO) AS FIC_IMPACTO,
            MAX(PCT_META_MAX_CONSUMIDA) AS MAIOR_PCT_META
        FROM gold_impacto_conjunto_dia
        WHERE {date_filter_sql}
        {conjunto_filter_sql}
    """
    summary = query_df(db_path, summary_sql).iloc[0]
    show_metric_cards(
        [
            ("Ocorrências", summary["OCORRENCIAS"], "Dia selecionado"),
            ("Conjuntos", summary["CONJUNTOS"], "Com impacto"),
            ("Maior % meta", summary["MAIOR_PCT_META"], "DEC ou FEC"),
        ]
    )

    st.markdown("### Ranking de ocorrências")
    ranking_sql = f"""
        SELECT
            DATA_OCORRENCIA,
            COD_CONJUNTO_ANEEL,
            REGIONAL,
            NUM_OCORRENCIA_ADMS,
            QTD_INTERRUPCOES,
            QTD_UCS_AFETADAS,
            TOTAL_UCS_CONJUNTO,
            DIC_IMPACTO,
            FIC_IMPACTO,
            DEC_IMPACTO_CONJUNTO,
            FEC_IMPACTO_CONJUNTO,
            META_DEC_CONJUNTO,
            META_FEC_CONJUNTO,
            PCT_META_DEC_CONSUMIDA,
            PCT_META_FEC_CONSUMIDA,
            PCT_META_MAX_CONSUMIDA
        FROM gold_impacto_conjunto_dia
        WHERE {date_filter_sql}
        {conjunto_filter_sql}
          AND COALESCE(PCT_META_MAX_CONSUMIDA, 0) >= {float(min_pct)}
        ORDER BY
            PCT_META_MAX_CONSUMIDA DESC,
            DIC_IMPACTO DESC,
            FIC_IMPACTO DESC
        LIMIT {int(sample_limit)}
    """
    ranking_df = query_df(db_path, ranking_sql)
    if ranking_df.empty:
        st.success("Nenhuma ocorrência encontrada para os filtros informados.")
        return

    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PCT_META_MAX_CONSUMIDA": st.column_config.ProgressColumn(
                "% máximo meta",
                min_value=0,
                max_value=100,
                format="%.2f%%",
            ),
            "PCT_META_DEC_CONSUMIDA": st.column_config.NumberColumn("% meta DEC", format="%.2f%%"),
            "PCT_META_FEC_CONSUMIDA": st.column_config.NumberColumn("% meta FEC", format="%.2f%%"),
        },
    )

    st.download_button(
        "Baixar ranking conjunto/dia",
        ranking_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"ranking_conjunto_dia_{selected_date}.csv",
        mime="text/csv",
    )

    st.markdown("### Resumo por conjunto no dia")
    conjunto_sql = f"""
        SELECT
            DATA_OCORRENCIA,
            COD_CONJUNTO_ANEEL,
            COUNT(*) AS OCORRENCIAS,
            SUM(QTD_UCS_AFETADAS) AS UCS_AFETADAS_SOMA,
            SUM(DIC_IMPACTO) AS DIC_IMPACTO,
            SUM(FIC_IMPACTO) AS FIC_IMPACTO,
            SUM(DEC_IMPACTO_CONJUNTO) AS DEC_DIA_CONJUNTO,
            SUM(FEC_IMPACTO_CONJUNTO) AS FEC_DIA_CONJUNTO,
            MAX(META_DEC_CONJUNTO) AS META_DEC_CONJUNTO,
            MAX(META_FEC_CONJUNTO) AS META_FEC_CONJUNTO,
            SUM(DEC_IMPACTO_CONJUNTO) / NULLIF(MAX(META_DEC_CONJUNTO), 0) * 100 AS PCT_META_DEC_DIA,
            SUM(FEC_IMPACTO_CONJUNTO) / NULLIF(MAX(META_FEC_CONJUNTO), 0) * 100 AS PCT_META_FEC_DIA
        FROM gold_impacto_conjunto_dia
        WHERE {date_filter_sql}
        {conjunto_filter_sql}
        GROUP BY DATA_OCORRENCIA, COD_CONJUNTO_ANEEL
        ORDER BY
            GREATEST(
                COALESCE(PCT_META_DEC_DIA, 0),
                COALESCE(PCT_META_FEC_DIA, 0)
            ) DESC
        LIMIT {int(sample_limit)}
    """
    st.dataframe(query_df(db_path, conjunto_sql), use_container_width=True, hide_index=True)


def show_analytics(db_path: str, sample_limit: int) -> None:
    st.subheader("Analytics Pós-Operação")
    st.caption(
        "Ranking estatístico para priorizar ocorrências que merecem verificação manual "
        "antes de aceitar a apuração e o ressarcimento."
    )

    required_tables = [
        "gold_apuracao_uc",
        "gold_ocorrencia_sem_uc",
        "gold_ressarcimento_prodist",
    ]
    if not all(require_table(db_path, table_name) for table_name in required_tables):
        return

    overview = analytics_overview(db_path).iloc[0]
    show_metric_cards(
        [
            ("Ocorrências", overview["OCORRENCIAS_APURAVEIS"], "Com UCs apuráveis"),
            ("Duração >= 24h", overview["LINHAS_DURACAO_GE_24H"], "Linhas UC com duração longa"),
            ("Ocorr. sem UC", overview["OCORRENCIAS_COM_INTERRUPCAO_SEM_UC"], "Com interrupção sem UC apurável"),
            ("Comp. estimada", overview["COMP_TOTAL_PRODIST"], "Soma PRODIST prévia"),
        ]
    )

    st.info(
        "`VALID_POS_OPERACAO = S` indica ocorrência já verificada e aceita pela pós-operação. "
        "Ela continua visível no ranking, mas deixa de ser tratada como pendência comum."
    )

    left, middle, right = st.columns([1, 1, 1])
    with left:
        min_score = st.slider(
            "Score mínimo",
            0,
            100,
            40,
            step=5,
            help="Score maior combina risco operacional, sem UC, duração alta e impacto financeiro.",
        )
    with middle:
        score_filter = st.selectbox(
            "Faixa de score",
            ["Todos", "Baixo", "Médio", "Alto", "Crítico"],
        )
    with right:
        validacao_filter = st.selectbox(
            "Validação Pós-Operação",
            ["Todos", "Somente validados", "Somente não validados"],
        )

    pendencia_filter = st.radio(
        "Pendência",
        ["Todos", "Pendentes", "Validados"],
        horizontal=True,
        help="Combina o score analytics com a validação operacional.",
    )

    ranking_df = analytics_occurrences(db_path, min_score, sample_limit * 5)
    if ranking_df.empty:
        st.success("Nenhuma ocorrência encontrada para o score informado.")
        return

    ranking_df["VALID_POS_OPERACAO"] = ranking_df["VALID_POS_OPERACAO"].fillna("N").astype(str).str.upper()

    if score_filter != "Todos":
        ranking_df = ranking_df[ranking_df["FAIXA_SCORE"] == score_filter]

    if validacao_filter == "Somente validados":
        ranking_df = ranking_df[ranking_df["VALID_POS_OPERACAO"] == "S"]
    elif validacao_filter == "Somente não validados":
        ranking_df = ranking_df[ranking_df["VALID_POS_OPERACAO"] != "S"]

    if pendencia_filter == "Pendentes":
        ranking_df = ranking_df[ranking_df["VALID_POS_OPERACAO"] != "S"]
    elif pendencia_filter == "Validados":
        ranking_df = ranking_df[ranking_df["VALID_POS_OPERACAO"] == "S"]

    ranking_df = ranking_df.head(sample_limit)
    if ranking_df.empty:
        st.success("Nenhuma ocorrência encontrada para os filtros informados.")
        return

    qtd_validadas = int((ranking_df["VALID_POS_OPERACAO"] == "S").sum())
    qtd_pendentes = int((ranking_df["VALID_POS_OPERACAO"] != "S").sum())
    qtd_criticas = int((ranking_df["FAIXA_SCORE"] == "Crítico").sum())
    qtd_criticas_pendentes = int(
        ((ranking_df["FAIXA_SCORE"] == "Crítico") & (ranking_df["VALID_POS_OPERACAO"] != "S")).sum()
    )

    show_metric_cards(
        [
            ("Ocorrências exibidas", len(ranking_df), "Após filtros do painel"),
            ("Validadas pós", qtd_validadas, "VALID_POS_OPERACAO = S"),
            ("Pendentes", qtd_pendentes, "VALID_POS_OPERACAO diferente de S"),
            ("Críticas pendentes", qtd_criticas_pendentes, "Score crítico ainda não validado"),
        ]
    )

    score_summary = (
        ranking_df.groupby(["FAIXA_SCORE", "VALID_POS_OPERACAO"], dropna=False)
        .size()
        .reset_index(name="QTD_OCORRENCIAS")
        .sort_values(["FAIXA_SCORE", "VALID_POS_OPERACAO"])
    )
    with st.expander("Resumo por faixa de score e validação", expanded=False):
        st.dataframe(score_summary, use_container_width=True, hide_index=True)
        st.caption(f"Ocorrências críticas no recorte: {qtd_criticas}.")

    st.markdown("#### Ocorrências prioritárias")
    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SCORE_PRIORIDADE": st.column_config.ProgressColumn(
                "SCORE",
                min_value=0,
                max_value=100,
            ),
            "FAIXA_SCORE": st.column_config.TextColumn("Faixa"),
            "VALID_POS_OPERACAO": st.column_config.TextColumn("Validado Pós"),
            "STATUS_ANALITICO": st.column_config.TextColumn("Status"),
            "COMP_TOTAL_PRODIST": st.column_config.NumberColumn("COMP_TOTAL_PRODIST", format="%.2f"),
            "DIC": st.column_config.NumberColumn("DIC", format="%.3f"),
            "MAX_DURACAO_H": st.column_config.NumberColumn("MAX_DURACAO_H", format="%.3f"),
        },
    )
    st.download_button(
        "Baixar ranking exibido",
        ranking_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="analytics_ocorrencias_prioritarias.csv",
        mime="text/csv",
    )

    selected_occurrence = st.selectbox(
        "Ocorrência para detalhar",
        ranking_df["NUM_OCORRENCIA_ADMS"].astype(str).tolist(),
    )
    selected_row = ranking_df[
        ranking_df["NUM_OCORRENCIA_ADMS"].astype(str) == str(selected_occurrence)
    ].iloc[0]
    st.markdown("#### Resumo da ocorrência selecionada")
    st.dataframe(pd.DataFrame([selected_row]), use_container_width=True, hide_index=True)

    st.markdown("#### Linhas UC/interrupção da ocorrência")
    detail_df = analytics_occurrence_detail(db_path, str(selected_occurrence), sample_limit)
    st.dataframe(detail_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Baixar detalhe da ocorrência",
        detail_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"analytics_ocorrencia_{selected_occurrence}.csv",
        mime="text/csv",
    )

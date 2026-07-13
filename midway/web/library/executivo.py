from __future__ import annotations

import altair as alt

from midway.auditoria.correcao_9282 import (
    adms_servicos_raw_path as correcao_9282_raw_path,
    calcular_correcao_9282,
    candidatos_automaticos_9282,
    candidatos_manuais_9282,
    gerar_exportacao_correcao_9282,
    registrar_ajustes_automaticos_9282_postgres,
    resumo_correcao_9282,
)
from midway.web.library.shared import *

alt.data_transformers.disable_max_rows()


def _total_consumidores_copel(db_path: str) -> float:
    if table_exists(db_path, "gold_consumidores"):
        total_df = query_df(
            db_path,
            """
            SELECT MAX(UC_FATURADA) AS TOTAL_CONSUMIDORES
            FROM gold_consumidores
            WHERE REGIONAL_TOTAL = 'COPEL'
            """,
        )
        if not total_df.empty and total_df.iloc[0]["TOTAL_CONSUMIDORES"]:
            return float(total_df.iloc[0]["TOTAL_CONSUMIDORES"])

    total_df = query_df(
        db_path,
        """
        SELECT COUNT(DISTINCT NUM_UC_UCI) AS TOTAL_CONSUMIDORES
        FROM gold_apuracao_uc
        """,
    )
    return float(total_df.iloc[0]["TOTAL_CONSUMIDORES"] or 0)


def _conjuntos_disponiveis(db_path: str) -> list[str]:
    if not table_exists(db_path, "gold_impacto_conjunto_dia"):
        return []

    conjuntos_df = query_df(
        db_path,
        """
        SELECT
            CAST(COD_CONJUNTO_ANEEL AS VARCHAR) AS COD_CONJUNTO_ANEEL,
            SUM(DIC_IMPACTO) AS DIC_IMPACTO
        FROM gold_impacto_conjunto_dia
        WHERE NULLIF(TRIM(CAST(COD_CONJUNTO_ANEEL AS VARCHAR)), '') IS NOT NULL
        GROUP BY 1
        ORDER BY DIC_IMPACTO DESC, COD_CONJUNTO_ANEEL
        """,
    )
    return conjuntos_df["COD_CONJUNTO_ANEEL"].astype(str).tolist()


def _copel_dec_fec(db_path: str, visualizacao: str) -> pd.DataFrame:
    total_consumidores = _total_consumidores_copel(db_path)
    if not total_consumidores:
        return pd.DataFrame(columns=["DATA_REFERENCIA", "INDICADOR", "VALOR"])

    diario_df = query_df(
        db_path,
        """
        SELECT
            CAST(DATA_HORA_INIC_INTRP AS DATE) AS DATA_REFERENCIA,
            SUM(CHI_LIQUIDO) AS DIC,
            SUM(CI_LIQUIDO) AS FIC
        FROM gold_apuracao_uc
        GROUP BY 1
        ORDER BY 1
        """,
    )
    if diario_df.empty:
        return pd.DataFrame(columns=["DATA_REFERENCIA", "INDICADOR", "VALOR"])

    diario_df["DEC"] = diario_df["DIC"].fillna(0) / total_consumidores
    diario_df["FEC"] = diario_df["FIC"].fillna(0) / total_consumidores
    diario_df = diario_df[["DATA_REFERENCIA", "DEC", "FEC"]]

    if visualizacao == "Acumulado diário":
        diario_df[["DEC", "FEC"]] = diario_df[["DEC", "FEC"]].cumsum()
    elif visualizacao == "Mensal":
        mensal_df = pd.DataFrame(
            [
                {
                    "DATA_REFERENCIA": "Mensal",
                    "DEC": diario_df["DEC"].sum(),
                    "FEC": diario_df["FEC"].sum(),
                }
            ]
        )
        diario_df = mensal_df

    return diario_df.melt(
        id_vars="DATA_REFERENCIA",
        value_vars=["DEC", "FEC"],
        var_name="INDICADOR",
        value_name="VALOR",
    )


def _conjunto_dec_fec(
    db_path: str,
    visualizacao: str,
    conjunto: str | None = None,
) -> pd.DataFrame:
    filtro_conjunto = ""
    if conjunto:
        filtro_conjunto = (
            "WHERE CAST(COD_CONJUNTO_ANEEL AS VARCHAR) = "
            f"{sql_literal_for_streamlit(conjunto)}"
        )

    diario_df = query_df(
        db_path,
        f"""
        SELECT
            DATA_OCORRENCIA AS DATA_REFERENCIA,
            CAST(COD_CONJUNTO_ANEEL AS VARCHAR) AS COD_CONJUNTO_ANEEL,
            SUM(DEC_IMPACTO_CONJUNTO) AS DEC,
            SUM(FEC_IMPACTO_CONJUNTO) AS FEC
        FROM gold_impacto_conjunto_dia
        {filtro_conjunto}
        GROUP BY 1, 2
        ORDER BY 2, 1
        """,
    )
    if diario_df.empty:
        return pd.DataFrame(columns=["DATA_REFERENCIA", "COD_CONJUNTO_ANEEL", "INDICADOR", "VALOR"])

    if visualizacao == "Acumulado diário":
        diario_df = diario_df.sort_values(["COD_CONJUNTO_ANEEL", "DATA_REFERENCIA"])
        diario_df[["DEC", "FEC"]] = diario_df.groupby("COD_CONJUNTO_ANEEL")[["DEC", "FEC"]].cumsum()
    elif visualizacao == "Mensal":
        diario_df = (
            diario_df.groupby("COD_CONJUNTO_ANEEL", as_index=False)[["DEC", "FEC"]]
            .sum()
            .assign(DATA_REFERENCIA="Mensal")
        )

    return diario_df.melt(
        id_vars=["DATA_REFERENCIA", "COD_CONJUNTO_ANEEL"],
        value_vars=["DEC", "FEC"],
        var_name="INDICADOR",
        value_name="VALOR",
    )


def _participacao_dec_fec_status(db_path: str) -> pd.DataFrame:
    total_consumidores = _total_consumidores_copel(db_path)
    ranking_df = analytics_occurrences(db_path, min_score=0, limit=1_000_000)
    if ranking_df.empty:
        return pd.DataFrame(columns=["INDICADOR", "STATUS_EXECUTIVO", "VALOR"])

    ranking_df = ranking_df.copy()
    ranking_df["STATUS_EXECUTIVO"] = ranking_df["SCORE_PRIORIDADE"].apply(
        lambda score: "Deve ser tratado" if float(score or 0) >= 60 else "Provável apurado"
    )
    ranking_df["DEC"] = ranking_df["DIC"].fillna(0) / total_consumidores if total_consumidores else 0
    ranking_df["FEC"] = ranking_df["FIC"].fillna(0) / total_consumidores if total_consumidores else 0

    indicadores_df = (
        ranking_df.groupby("STATUS_EXECUTIVO", as_index=False)[["DEC", "FEC"]]
        .sum()
        .melt(id_vars="STATUS_EXECUTIVO", var_name="INDICADOR", value_name="VALOR")
    )
    compensacao_df = _compensacao_unica_por_status(db_path, ranking_df)
    return pd.concat([indicadores_df, compensacao_df], ignore_index=True)


def _compensacao_unica_por_status(db_path: str, ranking_df: pd.DataFrame) -> pd.DataFrame:
    if not table_exists(db_path, "gold_ressarcimento_prodist"):
        return pd.DataFrame(columns=["STATUS_EXECUTIVO", "INDICADOR", "VALOR"])

    ocorrencia_score = ranking_df[["NUM_OCORRENCIA_ADMS", "SCORE_PRIORIDADE"]].copy()
    ocorrencia_score["NUM_OCORRENCIA_ADMS"] = ocorrencia_score["NUM_OCORRENCIA_ADMS"].astype(str)

    ocorrencia_uc = query_df(
        db_path,
        """
        SELECT DISTINCT
            CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
            CAST(NUM_UC_UCI AS VARCHAR) AS UC
        FROM gold_apuracao_uc
        WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
          AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
        """,
    )
    compensacao_uc = query_df(
        db_path,
        """
        SELECT
            CAST(UC AS VARCHAR) AS UC,
            COMP_TOTAL_PRODIST
        FROM gold_ressarcimento_prodist
        WHERE COALESCE(COMP_TOTAL_PRODIST, 0) > 0
        """,
    )
    if ocorrencia_uc.empty or compensacao_uc.empty:
        return pd.DataFrame(columns=["STATUS_EXECUTIVO", "INDICADOR", "VALOR"])

    uc_score = (
        ocorrencia_uc.merge(ocorrencia_score, on="NUM_OCORRENCIA_ADMS", how="left")
        .groupby("UC", as_index=False)["SCORE_PRIORIDADE"]
        .max()
    )
    compensacao_status = compensacao_uc.merge(uc_score, on="UC", how="left")
    compensacao_status["SCORE_PRIORIDADE"] = compensacao_status["SCORE_PRIORIDADE"].fillna(0)
    compensacao_status["STATUS_EXECUTIVO"] = compensacao_status["SCORE_PRIORIDADE"].apply(
        lambda score: "Deve ser tratado" if float(score or 0) >= 60 else "Provável apurado"
    )

    return (
        compensacao_status.groupby("STATUS_EXECUTIVO", as_index=False)["COMP_TOTAL_PRODIST"]
        .sum()
        .rename(columns={"COMP_TOTAL_PRODIST": "VALOR"})
        .assign(INDICADOR="COMPENSACAO")
    )


def _chart_copel_dec_fec(df: pd.DataFrame, visualizacao: str) -> alt.Chart:
    if visualizacao == "Mensal":
        return (
            alt.Chart(df)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("INDICADOR:N", title="Indicador"),
                y=alt.Y("VALOR:Q", title="Valor apurado"),
                color=alt.Color("INDICADOR:N", title="Indicador"),
                tooltip=[
                    alt.Tooltip("INDICADOR:N", title="Indicador"),
                    alt.Tooltip("VALOR:Q", title="Valor", format=".6f"),
                ],
            )
            .properties(height=320)
        )

    return (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("DATA_REFERENCIA:T", title="Dia"),
            y=alt.Y("VALOR:Q", title="Valor apurado"),
            color=alt.Color("INDICADOR:N", title="Indicador"),
            tooltip=[
                alt.Tooltip("DATA_REFERENCIA:T", title="Dia"),
                alt.Tooltip("INDICADOR:N", title="Indicador"),
                alt.Tooltip("VALOR:Q", title="Valor", format=".6f"),
            ],
        )
        .properties(height=320)
        .interactive()
    )


def _chart_conjunto_dec_fec(df: pd.DataFrame, visualizacao: str, todos: bool) -> alt.Chart:
    if visualizacao == "Mensal":
        chart = (
            alt.Chart(df)
            .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
            .encode(
                x=alt.X("COD_CONJUNTO_ANEEL:N", title="Conjunto", sort="-y"),
                xOffset=alt.XOffset("INDICADOR:N"),
                y=alt.Y("VALOR:Q", title="Valor apurado"),
                color=alt.Color("INDICADOR:N", title="Indicador"),
                tooltip=[
                    alt.Tooltip("COD_CONJUNTO_ANEEL:N", title="Conjunto"),
                    alt.Tooltip("INDICADOR:N", title="Indicador"),
                    alt.Tooltip("VALOR:Q", title="Valor", format=".6f"),
                ],
            )
            .properties(height=360)
        )
        return chart.interactive()

    if todos:
        return (
            alt.Chart(df)
            .mark_line(point=False)
            .encode(
                x=alt.X("DATA_REFERENCIA:T", title="Dia"),
                y=alt.Y("VALOR:Q", title="Valor apurado"),
                color=alt.Color("COD_CONJUNTO_ANEEL:N", title="Conjunto"),
                tooltip=[
                    alt.Tooltip("DATA_REFERENCIA:T", title="Dia"),
                    alt.Tooltip("COD_CONJUNTO_ANEEL:N", title="Conjunto"),
                    alt.Tooltip("INDICADOR:N", title="Indicador"),
                    alt.Tooltip("VALOR:Q", title="Valor", format=".6f"),
                ],
            )
            .properties(width=420, height=300)
            .facet(column=alt.Column("INDICADOR:N", title=None))
            .resolve_scale(y="independent")
        )

    return (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X("DATA_REFERENCIA:T", title="Dia"),
            y=alt.Y("VALOR:Q", title="Valor apurado"),
            color=alt.Color("INDICADOR:N", title="Indicador"),
            tooltip=[
                alt.Tooltip("DATA_REFERENCIA:T", title="Dia"),
                alt.Tooltip("COD_CONJUNTO_ANEEL:N", title="Conjunto"),
                alt.Tooltip("INDICADOR:N", title="Indicador"),
                alt.Tooltip("VALOR:Q", title="Valor", format=".6f"),
            ],
        )
        .properties(height=320)
        .interactive()
    )


def _pie_chart(df: pd.DataFrame, indicador: str, titulo: str, formato: str = ".6f") -> alt.Chart:
    chart_df = df[df["INDICADOR"] == indicador].copy()
    return (
        alt.Chart(chart_df)
        .mark_arc(innerRadius=55)
        .encode(
            theta=alt.Theta("VALOR:Q", title=indicador),
            color=alt.Color("STATUS_EXECUTIVO:N", title="Status"),
            tooltip=[
                alt.Tooltip("STATUS_EXECUTIVO:N", title="Status"),
                alt.Tooltip("VALOR:Q", title=titulo, format=formato),
            ],
        )
        .properties(height=300, title=titulo)
    )


@st.cache_data(show_spinner=False)
def _correcao_9282_cached(anomes: str, db_path: str, raw_path: str) -> pd.DataFrame:
    return calcular_correcao_9282(anomes, db_path, raw_path)


def _show_correcao_9282(anomes: str, db_path: str, sample_limit: int) -> None:
    st.subheader("Tratativa RA 92/82")
    st.caption(
        "Classifica ocorrências RA com componente 92 e causa 82. "
        "Serviço ADMS válido prevalece; sem serviço válido, usa a melhor coincidência "
        "entre reclamação e referência grupo/componente/causa."
    )

    raw_path = correcao_9282_raw_path(anomes)
    if not raw_path.exists():
        st.info(
            "RAW de serviços ADMS não encontrado. Execute "
            f"`run.bat extrair_adms_servicos` para gerar `{raw_path}`."
        )
        return

    required_tables = [
        "gold_interrupcao_tratada",
        "gold_apuracao_uc",
        "gold_reclamacao_uc_vinculada",
        "gold_reclamacao_ocorrencia_resumo",
        "gold_iqs_referencia_componente_causa",
    ]
    missing = [table for table in required_tables if not table_exists(db_path, table)]
    if missing:
        st.info(
            "Tabelas necessárias não encontradas: "
            + ", ".join(f"`{table}`" for table in missing)
            + ". Execute apuração, reclamações DBGUO e referência IQS."
        )
        return

    df = _correcao_9282_cached(anomes, db_path, str(raw_path))
    if df.empty:
        st.success("Nenhum caso RA 92/82 encontrado.")
        return

    automaticos = candidatos_automaticos_9282(df)
    manuais = candidatos_manuais_9282(df)
    with_suggestion = int(df["COD_CAUSA_SUGERIDA"].astype(str).str.len().gt(0).sum())
    show_metric_cards(
        [
            ("RA 92/82", format_number(df["NUM_SEQ_INTRP"].nunique(), 0), "Interrupções"),
            ("Automático autorizado", format_number(len(automaticos), 0), "Serviço robusto"),
            ("Fila técnica/manual", format_number(len(manuais), 0), "Conflito ou reclamação"),
            ("Sem ação automática", format_number(len(df) - len(automaticos) - len(manuais), 0), "Sem evidência"),
            (
                "Fonte serviço",
                format_number(df["FONTE_SUGESTAO"].eq("SERVICO").sum(), 0),
                "Inclui conflitos",
            ),
            (
                "Com sugestão",
                format_number(with_suggestion, 0),
                "Algoritmo",
            ),
        ]
    )

    st.caption(
        "Premissa operacional: o Executivo autoriza a tratativa em massa somente dos automáticos; "
        "o Ajuste Manual fica para o técnico tratar registros problemáticos com evidências adicionais. "
        f"RAW serviços: `{raw_path}`"
    )

    tabs = st.tabs(["Autorização em massa", "Fila técnica", "Resumo algoritmo", "Ranking RA 92/82", "Exportação"])
    with tabs[0]:
        st.markdown("### Automáticos para autorização executiva")
        st.caption("Critério: `FONTE_SUGESTAO = SERVICO`, `NIVEL_EVIDENCIA = ROBUSTA` e par válido na referência IQS.")
        if automaticos.empty:
            st.info("Nenhum ajuste automático elegível.")
        else:
            st.dataframe(
                automaticos.head(sample_limit),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "SCORE_SUGESTAO": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                    "DIC_OCORRENCIA": st.column_config.NumberColumn("DIC", format="%.3f"),
                    "FIC_OCORRENCIA": st.column_config.NumberColumn("FIC", format="%.3f"),
                },
            )
            st.warning(
                "Ao autorizar, estes registros serão gravados no PostgreSQL como ajustes aprovados "
                "e os casos problemáticos serão enviados para a fila técnica."
            )
            if st.button("Autorizar ajustes automáticos 92/82", type="primary"):
                try:
                    resultado = registrar_ajustes_automaticos_9282_postgres(anomes, db_path, raw_path)
                    st.success(
                        "Autorização concluída: "
                        f"{resultado['criados']} ajuste(s) criado(s), "
                        f"{resultado['ignorados']} duplicado(s) ignorado(s), "
                        f"{resultado['manuais_criados']} item(ns) incluído(s) na fila técnica. "
                        f"ID autorização: {resultado['id_autorizacao']}."
                    )
                    st.cache_data.clear()
                except Exception as error:
                    st.error(f"Falha ao autorizar ajustes automáticos: {error}")

    with tabs[1]:
        st.markdown("### Fila técnica para Ajuste Manual")
        st.caption("Casos com conflito de serviço ou evidência baseada em reclamação ficam para análise técnica.")
        if manuais.empty:
            st.success("Nenhum caso manual/problemático identificado.")
        else:
            st.dataframe(
                manuais.head(sample_limit),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "SCORE_SUGESTAO": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                    "DIC_OCORRENCIA": st.column_config.NumberColumn("DIC", format="%.3f"),
                    "FIC_OCORRENCIA": st.column_config.NumberColumn("FIC", format="%.3f"),
                },
            )
            st.download_button(
                "Baixar fila técnica 92/82",
                manuais.to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name=f"correcao_ra_9282_{anomes}_fila_tecnica.csv",
                mime="text/csv",
            )

    with tabs[2]:
        resumo = resumo_correcao_9282(df)
        st.dataframe(
            resumo,
            use_container_width=True,
            hide_index=True,
            column_config={
                "DIC_TOTAL": st.column_config.NumberColumn("DIC total", format="%.3f"),
            },
        )
        st.download_button(
            "Baixar resumo 92/82",
            resumo.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name=f"correcao_ra_9282_{anomes}_resumo.csv",
            mime="text/csv",
        )

    with tabs[3]:
        col_action, col_source, col_score = st.columns([2, 2, 1])
        with col_action:
            action = st.selectbox(
                "Ação",
                ["Todas"] + sorted(df["ACAO_RECOMENDADA"].dropna().astype(str).unique().tolist()),
            )
        with col_source:
            source = st.selectbox(
                "Fonte",
                ["Todas"] + sorted(df["FONTE_SUGESTAO"].dropna().astype(str).unique().tolist()),
            )
        with col_score:
            min_score = st.slider("Score mínimo", 0, 100, 0, step=5, key="executivo_9282_score")

        filtered = df.copy()
        if action != "Todas":
            filtered = filtered[filtered["ACAO_RECOMENDADA"].astype(str).eq(action)]
        if source != "Todas":
            filtered = filtered[filtered["FONTE_SUGESTAO"].astype(str).eq(source)]
        filtered = filtered[filtered["SCORE_SUGESTAO"].fillna(0).astype(float) >= min_score]
        filtered = filtered.sort_values(
            ["SCORE_SUGESTAO", "DIC_OCORRENCIA", "QTD_RECLAMACOES"],
            ascending=[False, False, False],
        ).head(int(sample_limit))

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
            column_config={
                "SCORE_SUGESTAO": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                "DIC_OCORRENCIA": st.column_config.NumberColumn("DIC", format="%.3f"),
                "FIC_OCORRENCIA": st.column_config.NumberColumn("FIC", format="%.3f"),
            },
        )
        st.download_button(
            "Baixar ranking 92/82",
            filtered.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name=f"correcao_ra_9282_{anomes}_ranking.csv",
            mime="text/csv",
        )

    with tabs[4]:
        st.markdown("Gera os arquivos em `data/export/correcao_9282` com detalhe, resumo, nota da regra e CSV IQS por regional.")
        if st.button("Gerar arquivo correcao_9282", type="primary"):
            result = gerar_exportacao_correcao_9282(anomes, db_path, raw_path)
            st.success(
                "Arquivos gerados: "
                f"`{result['detalhe']}`, `{result['resumo']}`, `{result['nota']}`."
            )


def _show_executivo_geral(db_path: str, sample_limit: int) -> None:
    st.subheader("Dashboard Executivo")
    st.caption(
        "Resumo executivo da qualidade do tratamento, impacto em continuidade, "
        "dia crítico provável, ISE simulado e compensação estimada."
    )

    overview = analytics_overview(db_path)
    if not overview.empty:
        row = overview.iloc[0].to_dict()
        show_metric_cards(
            [
                ("Ocorrências apuráveis", row.get("OCORRENCIAS_APURAVEIS"), "DEC/FEC"),
                ("UCs apuráveis", row.get("UCS_APURAVEIS"), "Base DIC/FIC"),
                ("DIC líquido", row.get("DIC_TOTAL"), "Horas"),
                ("FIC líquido", row.get("FIC_TOTAL"), "Interrupções"),
                ("Compensação estimada", row.get("COMP_TOTAL_PRODIST"), "R$"),
            ]
        )

    if require_table(db_path, "gold_apuracao_uc") and table_exists(
        db_path, "gold_impacto_conjunto_dia"
    ):
        st.markdown("### DEC/FEC COPEL")
        st.caption("Visão consolidada da COPEL, com opção diária, acumulada diária ou mensal.")

        visualizacao_copel = st.radio(
            "Visualização COPEL",
            ["Diário", "Acumulado diário", "Mensal"],
            horizontal=True,
            key="executivo_visualizacao_copel",
        )
        copel_df = _copel_dec_fec(db_path, visualizacao_copel)
        if copel_df.empty:
            st.info("Nenhum dado disponível para DEC/FEC COPEL.")
        else:
            st.altair_chart(
                _chart_copel_dec_fec(copel_df, visualizacao_copel),
                use_container_width=True,
            )

        st.markdown("### DEC/FEC por conjuntos")
        st.caption(
            "Mostra todos os conjuntos ou um conjunto selecionado. "
            "No diário, mostra dia a dia; no acumulado diário, acumula os dias do mês; "
            "no mensal, consolida o mês."
        )

        conjuntos = _conjuntos_disponiveis(db_path)
        if conjuntos:
            left, middle = st.columns([1, 1])
            with left:
                visualizacao_conjunto = st.radio(
                    "Visualização conjuntos",
                    ["Diário", "Acumulado diário", "Mensal"],
                    horizontal=True,
                    key="executivo_visualizacao_conjunto",
                )
            with middle:
                modo_conjunto = st.radio(
                    "Conjuntos",
                    ["Todos os conjuntos", "Selecionar um conjunto"],
                    horizontal=True,
                    key="executivo_modo_conjunto",
                )

            selected_conjunto = None
            if modo_conjunto == "Selecionar um conjunto":
                selected_conjunto = st.selectbox("Conjunto elétrico", conjuntos)

            conjunto_df = _conjunto_dec_fec(
                db_path,
                visualizacao_conjunto,
                selected_conjunto,
            )
            if conjunto_df.empty:
                st.info("Nenhum dado disponível para os filtros de conjunto.")
            else:
                st.altair_chart(
                    _chart_conjunto_dec_fec(
                        conjunto_df,
                        visualizacao_conjunto,
                        todos=selected_conjunto is None,
                    ),
                    use_container_width=True,
                )

            status_df = _participacao_dec_fec_status(db_path)
            if not status_df.empty:
                st.markdown("### Participação provável x tratar")
                st.caption(
                    "Classificação executiva: ocorrências com score de prioridade maior ou igual a 60 "
                    "entram como `Deve ser tratado`; as demais ficam como `Provável apurado`."
                )
                left, middle, right = st.columns(3)
                with left:
                    st.altair_chart(_pie_chart(status_df, "DEC", "DEC"), use_container_width=True)
                with middle:
                    st.altair_chart(_pie_chart(status_df, "FEC", "FEC"), use_container_width=True)
                with right:
                    st.altair_chart(
                        _pie_chart(
                            status_df,
                            "COMPENSACAO",
                            "Compensação estimada",
                            ",.2f",
                        ),
                        use_container_width=True,
                    )
        else:
            st.info("Nenhum conjunto disponível em `gold_impacto_conjunto_dia`.")

    if table_exists(db_path, "gold_impacto_conjunto_dia"):
        st.markdown("### Top conjuntos por impacto diário")
        conjunto_sql = f"""
            SELECT
                DATA_OCORRENCIA,
                COD_CONJUNTO_ANEEL,
                REGIONAL,
                NUM_OCORRENCIA_ADMS,
                QTD_INTERRUPCOES,
                QTD_UCS_AFETADAS,
                DIC_IMPACTO,
                FIC_IMPACTO,
                PCT_META_MAX_CONSUMIDA
            FROM gold_impacto_conjunto_dia
            ORDER BY PCT_META_MAX_CONSUMIDA DESC, DIC_IMPACTO DESC
            LIMIT {int(sample_limit)}
        """
        st.dataframe(query_df(db_path, conjunto_sql), use_container_width=True, hide_index=True)
    else:
        st.info("Execute `run.bat apuracao_parcial` para gerar impacto por conjunto.")

    if table_exists(db_path, "gold_meta_dia_critico_conjunto") and table_exists(
        db_path, "gold_impacto_conjunto_dia"
    ):
        st.markdown("### Dias críticos prováveis")
        dia_critico_sql = f"""
            SELECT
                i.DATA_OCORRENCIA,
                i.COD_CONJUNTO_ANEEL,
                i.REGIONAL,
                COUNT(DISTINCT i.NUM_OCORRENCIA_ADMS) AS OCORRENCIAS,
                SUM(i.DIC_IMPACTO) AS DIC_IMPACTO,
                SUM(i.FIC_IMPACTO) AS FIC_IMPACTO,
                MAX(m.META_DIA_CRITICO_SINTETICA) AS META_DIA_CRITICO_SINTETICA,
                CASE
                    WHEN MAX(m.META_DIA_CRITICO_SINTETICA) > 0
                    THEN COUNT(DISTINCT i.NUM_OCORRENCIA_ADMS) / MAX(m.META_DIA_CRITICO_SINTETICA) * 100
                    ELSE NULL
                END AS PCT_META_DIA_CRITICO
            FROM gold_impacto_conjunto_dia i
            LEFT JOIN gold_meta_dia_critico_conjunto m
              ON TRIM(CAST(m.COD_CONJUNTO_ANEEL AS VARCHAR)) = TRIM(CAST(i.COD_CONJUNTO_ANEEL AS VARCHAR))
            GROUP BY
                i.DATA_OCORRENCIA,
                i.COD_CONJUNTO_ANEEL,
                i.REGIONAL
            ORDER BY PCT_META_DIA_CRITICO DESC, OCORRENCIAS DESC
            LIMIT {int(sample_limit)}
        """
        st.dataframe(query_df(db_path, dia_critico_sql), use_container_width=True, hide_index=True)


def show_executivo(db_path: str, sample_limit: int, anomes: str | None = None) -> None:
    tabs = st.tabs(["Executivo", "9282"])
    with tabs[0]:
        _show_executivo_geral(db_path, sample_limit)
    with tabs[1]:
        _show_correcao_9282(anomes or DEFAULT_ANOMES, db_path, sample_limit)

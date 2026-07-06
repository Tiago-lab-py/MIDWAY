from __future__ import annotations

from midway.web.library.shared import *


def show_dia_critico(db_path: str, sample_limit: int) -> None:
    st.subheader("Verificação de Dia Crítico por Conjunto")
    st.caption(
        "Triagem estatística para identificar dias/conjuntos com muitas ocorrências de longa duração. "
        "Como a base não possui serviços/equipes, a duração da ocorrência é usada como aproximação."
    )

    required_tables = [
        "gold_impacto_conjunto_dia",
        "gold_meta_dia_critico_conjunto",
    ]
    if not all(require_table(db_path, table_name) for table_name in required_tables):
        st.info(
            "Execute `run.bat apuracao_parcial` para gerar "
            "`gold_impacto_conjunto_dia` e `gold_meta_dia_critico_conjunto`."
        )
        return

    st.info(
        "Meta sintética provisória: `1,5 x MAX(META_DICRI)` das UCs urbanas do conjunto. "
        "A coluna `META_DIA_CRITICO_REAL` fica pendente para substituição futura pela meta real."
    )

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
        selected_date = st.selectbox("Dia", dates_df["DATA_OCORRENCIA"].tolist(), key="dia_critico_data")
    with middle:
        conjunto_options = ["Todos"] + conjuntos_df["COD_CONJUNTO_ANEEL"].astype(str).tolist()
        selected_conjunto = st.selectbox("Conjunto", conjunto_options, key="dia_critico_conjunto")
    with right:
        min_duration = st.slider(
            "Duração mínima provável atendimento (h)",
            0.25,
            24.0,
            1.0,
            step=0.25,
            help="Ocorrências com duração máxima igual ou superior ao valor entram na contagem.",
        )

    date_filter_sql = f"CAST(i.DATA_OCORRENCIA AS VARCHAR) = {sql_literal_for_streamlit(selected_date)}"
    conjunto_filter_sql = ""
    if selected_conjunto != "Todos":
        conjunto_filter_sql = (
            " AND CAST(i.COD_CONJUNTO_ANEEL AS VARCHAR) = "
            f"{sql_literal_for_streamlit(selected_conjunto)}"
        )

    base_sql = f"""
        WITH diario AS (
            SELECT
                i.DATA_OCORRENCIA,
                i.COD_CONJUNTO_ANEEL,
                COUNT(DISTINCT i.NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS_PROVAVEL_EQUIPE,
                SUM(i.QTD_UCS_AFETADAS) AS UCS_AFETADAS_SOMA,
                SUM(i.DIC_IMPACTO) AS DIC_IMPACTO,
                SUM(i.FIC_IMPACTO) AS FIC_IMPACTO,
                MAX(i.MAX_DURACAO_H) AS MAX_DURACAO_H
            FROM gold_impacto_conjunto_dia i
            WHERE {date_filter_sql}
            {conjunto_filter_sql}
              AND COALESCE(i.MAX_DURACAO_H, 0) >= {float(min_duration)}
            GROUP BY i.DATA_OCORRENCIA, i.COD_CONJUNTO_ANEEL
        ),
        comparativo AS (
            SELECT
                d.DATA_OCORRENCIA,
                d.COD_CONJUNTO_ANEEL,
                d.QTD_OCORRENCIAS_PROVAVEL_EQUIPE,
                d.UCS_AFETADAS_SOMA,
                d.DIC_IMPACTO,
                d.FIC_IMPACTO,
                d.MAX_DURACAO_H,
                m.QTD_UCS_URBANAS,
                m.META_DICRI_UC_URBANA_REFERENCIA,
                m.FATOR_META_DIA_CRITICO_SINTETICA,
                m.META_DIA_CRITICO_SINTETICA,
                m.META_DIA_CRITICO_REAL,
                CASE
                    WHEN m.META_DIA_CRITICO_REAL IS NOT NULL THEN m.META_DIA_CRITICO_REAL
                    ELSE m.META_DIA_CRITICO_SINTETICA
                END AS META_DIA_CRITICO_USADA,
                CASE
                    WHEN m.META_DIA_CRITICO_REAL IS NOT NULL THEN 'REAL'
                    ELSE 'SINTETICA'
                END AS TIPO_META_USADA,
                m.PENDENCIA_META_REAL
            FROM diario d
            LEFT JOIN gold_meta_dia_critico_conjunto m
              ON CAST(m.COD_CONJUNTO_ANEEL AS VARCHAR) = CAST(d.COD_CONJUNTO_ANEEL AS VARCHAR)
        )
        SELECT
            *,
            QTD_OCORRENCIAS_PROVAVEL_EQUIPE / NULLIF(META_DIA_CRITICO_USADA, 0) * 100
                AS PCT_META_DIA_CRITICO,
            CASE
                WHEN QTD_OCORRENCIAS_PROVAVEL_EQUIPE / NULLIF(META_DIA_CRITICO_USADA, 0) * 100 >= 100
                THEN 'ACIMA_REFERENCIA'
                WHEN QTD_OCORRENCIAS_PROVAVEL_EQUIPE / NULLIF(META_DIA_CRITICO_USADA, 0) * 100 >= 80
                THEN 'ATENCAO'
                ELSE 'MONITORAR'
            END AS STATUS_DIA_CRITICO
        FROM comparativo
    """

    ranking_sql = f"""
        SELECT *
        FROM ({base_sql}) base
        ORDER BY
            PCT_META_DIA_CRITICO DESC NULLS LAST,
            QTD_OCORRENCIAS_PROVAVEL_EQUIPE DESC,
            DIC_IMPACTO DESC
        LIMIT {int(sample_limit)}
    """
    ranking_df = query_df(db_path, ranking_sql)
    if ranking_df.empty:
        st.success("Nenhum conjunto/dia atingiu o tempo mínimo selecionado.")
        return

    summary_sql = f"""
        SELECT
            SUM(QTD_OCORRENCIAS_PROVAVEL_EQUIPE) AS QTD_OCORRENCIAS_PROVAVEL_EQUIPE,
            COUNT(DISTINCT COD_CONJUNTO_ANEEL) AS CONJUNTOS,
            MAX(PCT_META_DIA_CRITICO) AS PCT_META_DIA_CRITICO
        FROM ({base_sql}) base
    """
    resumo = query_df(db_path, summary_sql).iloc[0]
    show_metric_cards(
        [
            ("Prováveis atendimentos", resumo["QTD_OCORRENCIAS_PROVAVEL_EQUIPE"], f"Duração >= {min_duration:.2f}h"),
            ("Conjuntos", resumo["CONJUNTOS"], "Com ocorrência no recorte"),
            ("Maior % meta crítica", resumo["PCT_META_DIA_CRITICO"], "Referência sintética/real"),
        ]
    )

    st.markdown("### Comparativo por dia e conjunto")
    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PCT_META_DIA_CRITICO": st.column_config.ProgressColumn(
                "% meta dia crítico",
                min_value=0,
                max_value=100,
                format="%.2f%%",
            ),
            "META_DIA_CRITICO_SINTETICA": st.column_config.NumberColumn("Meta sintética", format="%.2f"),
            "META_DIA_CRITICO_REAL": st.column_config.NumberColumn("Meta real", format="%.2f"),
            "MAX_DURACAO_H": st.column_config.NumberColumn("Máx. duração h", format="%.2f"),
        },
    )
    st.download_button(
        "Baixar comparativo de dia crítico",
        ranking_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"dia_critico_conjunto_{selected_date}.csv",
        mime="text/csv",
    )

    st.markdown("### Ocorrências consideradas no critério")
    detail_sql = f"""
        SELECT
            i.DATA_OCORRENCIA,
            i.COD_CONJUNTO_ANEEL,
            i.REGIONAL,
            i.NUM_OCORRENCIA_ADMS,
            i.QTD_INTERRUPCOES,
            i.QTD_UCS_AFETADAS,
            i.MAX_DURACAO_H,
            i.DIC_IMPACTO,
            i.FIC_IMPACTO,
            i.PCT_META_MAX_CONSUMIDA
        FROM gold_impacto_conjunto_dia i
        WHERE {date_filter_sql}
        {conjunto_filter_sql}
          AND COALESCE(i.MAX_DURACAO_H, 0) >= {float(min_duration)}
        ORDER BY
            i.MAX_DURACAO_H DESC,
            i.DIC_IMPACTO DESC,
            i.FIC_IMPACTO DESC
        LIMIT {int(sample_limit)}
    """
    st.dataframe(query_df(db_path, detail_sql), use_container_width=True, hide_index=True)

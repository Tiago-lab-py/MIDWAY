from __future__ import annotations

import altair as alt

from midway.web.library.shared import *


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


def _dec_fec_comparativo(db_path: str, conjunto: str) -> pd.DataFrame:
    total_consumidores = _total_consumidores_copel(db_path)
    copel_df = query_df(
        db_path,
        """
        SELECT
            SUM(CHI_LIQUIDO) AS DIC,
            SUM(CI_LIQUIDO) AS FIC
        FROM gold_apuracao_uc
        """,
    )
    copel_dic = float(copel_df.iloc[0]["DIC"] or 0)
    copel_fic = float(copel_df.iloc[0]["FIC"] or 0)

    conjunto_df = query_df(
        db_path,
        f"""
        SELECT
            SUM(DEC_IMPACTO_CONJUNTO) AS DEC,
            SUM(FEC_IMPACTO_CONJUNTO) AS FEC
        FROM gold_impacto_conjunto_dia
        WHERE CAST(COD_CONJUNTO_ANEEL AS VARCHAR) = {sql_literal_for_streamlit(conjunto)}
        """,
    )
    conjunto_dec = float(conjunto_df.iloc[0]["DEC"] or 0)
    conjunto_fec = float(conjunto_df.iloc[0]["FEC"] or 0)

    return pd.DataFrame(
        [
            {"ESCOPO": "COPEL", "INDICADOR": "DEC", "VALOR": copel_dic / total_consumidores if total_consumidores else 0},
            {"ESCOPO": "COPEL", "INDICADOR": "FEC", "VALOR": copel_fic / total_consumidores if total_consumidores else 0},
            {"ESCOPO": f"Conjunto {conjunto}", "INDICADOR": "DEC", "VALOR": conjunto_dec},
            {"ESCOPO": f"Conjunto {conjunto}", "INDICADOR": "FEC", "VALOR": conjunto_fec},
        ]
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

    return (
        ranking_df.groupby("STATUS_EXECUTIVO", as_index=False)[["DEC", "FEC"]]
        .sum()
        .melt(id_vars="STATUS_EXECUTIVO", var_name="INDICADOR", value_name="VALOR")
    )


def _bar_chart_dec_fec(df: pd.DataFrame) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("ESCOPO:N", title="Escopo"),
            xOffset=alt.XOffset("INDICADOR:N"),
            y=alt.Y("VALOR:Q", title="Valor apurado"),
            color=alt.Color("INDICADOR:N", title="Indicador"),
            tooltip=[
                alt.Tooltip("ESCOPO:N", title="Escopo"),
                alt.Tooltip("INDICADOR:N", title="Indicador"),
                alt.Tooltip("VALOR:Q", title="Valor", format=".6f"),
            ],
        )
        .properties(height=320)
    )


def _pie_chart(df: pd.DataFrame, indicador: str) -> alt.Chart:
    chart_df = df[df["INDICADOR"] == indicador].copy()
    return (
        alt.Chart(chart_df)
        .mark_arc(innerRadius=55)
        .encode(
            theta=alt.Theta("VALOR:Q", title=indicador),
            color=alt.Color("STATUS_EXECUTIVO:N", title="Status"),
            tooltip=[
                alt.Tooltip("STATUS_EXECUTIVO:N", title="Status"),
                alt.Tooltip("VALOR:Q", title=indicador, format=".6f"),
            ],
        )
        .properties(height=300)
    )


def show_executivo(db_path: str, sample_limit: int) -> None:
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
        st.markdown("### DEC/FEC executivo")
        st.caption(
            "Compara o DEC/FEC acumulado da COPEL com o conjunto selecionado. "
            "O conjunto sugerido inicialmente é o de maior impacto em DIC."
        )

        conjuntos = _conjuntos_disponiveis(db_path)
        if conjuntos:
            selected_conjunto = st.selectbox("Conjunto elétrico", conjuntos)
            dec_fec_df = _dec_fec_comparativo(db_path, selected_conjunto)
            st.altair_chart(_bar_chart_dec_fec(dec_fec_df), use_container_width=True)

            status_df = _participacao_dec_fec_status(db_path)
            if not status_df.empty:
                st.markdown("### Participação provável x tratar")
                st.caption(
                    "Classificação executiva: ocorrências com score de prioridade maior ou igual a 60 "
                    "entram como `Deve ser tratado`; as demais ficam como `Provável apurado`."
                )
                left, right = st.columns(2)
                with left:
                    st.altair_chart(_pie_chart(status_df, "DEC"), use_container_width=True)
                with right:
                    st.altair_chart(_pie_chart(status_df, "FEC"), use_container_width=True)
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

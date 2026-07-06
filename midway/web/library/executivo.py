from __future__ import annotations

from midway.web.library.shared import *


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

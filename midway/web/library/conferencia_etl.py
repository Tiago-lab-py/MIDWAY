from __future__ import annotations

from midway.web.library.shared import *


def show_quality_metrics(anomes: str) -> None:
    st.subheader("Métricas de Qualidade")
    metrics_file = latest_file(f"Metricas_Qualidade_Dados_{anomes}_*.CSV")
    summary_file = latest_file(f"Metricas_Qualidade_Dados_{anomes}_*_RESUMO.TXT")

    if not metrics_file:
        st.info("Nenhum arquivo de métricas encontrado. Rode `run.bat metricas_qualidade`.")
        return

    metrics_df = read_csv_preview(str(metrics_file), 5000)
    metrics_df.columns = [str(column).strip().upper() for column in metrics_df.columns]
    severity_column = next(
        (column for column in ("SEVERIDADE", "NIVEL") if column in metrics_df.columns),
        None,
    )

    total = len(metrics_df)
    critical = int((metrics_df[severity_column] == "CRITICO").sum()) if severity_column else 0
    alerts = int((metrics_df[severity_column] == "ALERTA").sum()) if severity_column else 0

    show_metric_cards(
        [
            ("Métricas", total, None),
            ("Críticos", critical, "Bloqueiam fechamento"),
            ("Alertas", alerts, "Exigem auditoria"),
        ]
    )

    if summary_file:
        with st.expander("Resumo TXT", expanded=critical > 0):
            st.code(read_text(str(summary_file)))

    if severity_column:
        selected = st.multiselect(
            "Severidade",
            sorted(metrics_df[severity_column].dropna().unique()),
            default=sorted(metrics_df[severity_column].dropna().unique()),
        )
        if selected:
            metrics_df = metrics_df[metrics_df[severity_column].isin(selected)]

    st.dataframe(metrics_df, use_container_width=True, hide_index=True)


def show_overlaps(db_path: str, sample_limit: int) -> None:
    st.subheader("Sobreposição Residual")

    if not require_table(db_path, "gold_apuracao_uc"):
        return

    total_sql = """
        WITH base AS (
            SELECT
                TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS UC,
                TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) AS COD_TIPO_INTRP,
                TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) AS TIPO_PROTOC_JUSTIF_UCI,
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                DTHR_INICIO_INTRP_UC,
                DATA_HORA_FIM_INTRP,
                DURACAO_HORA,
                LAG(DATA_HORA_FIM_INTRP) OVER (
                    PARTITION BY
                        TRIM(CAST(NUM_UC_UCI AS VARCHAR)),
                        TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)),
                        TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR))
                    ORDER BY
                        DTHR_INICIO_INTRP_UC,
                        DATA_HORA_FIM_INTRP,
                        TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                ) AS FIM_ANTERIOR
            FROM gold_apuracao_uc
            WHERE CI_LIQUIDO = 1
        )
        SELECT COUNT(*) AS SOBREPOSICOES_RESIDUAIS
        FROM base
        WHERE FIM_ANTERIOR > DTHR_INICIO_INTRP_UC
    """
    total = query_df(db_path, total_sql).iloc[0, 0]
    st.metric("Sobreposições residuais líquidas", format_number(total))

    sample_sql = f"""
        WITH base AS (
            SELECT
                TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS UC,
                TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)) AS COD_TIPO_INTRP,
                TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) AS TIPO_PROTOC_JUSTIF_UCI,
                TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                DTHR_INICIO_INTRP_UC,
                DATA_HORA_FIM_INTRP,
                DURACAO_HORA,
                CHI_LIQUIDO,
                LAG(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))) OVER (
                    PARTITION BY
                        TRIM(CAST(NUM_UC_UCI AS VARCHAR)),
                        TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)),
                        TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR))
                    ORDER BY DTHR_INICIO_INTRP_UC, DATA_HORA_FIM_INTRP, TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                ) AS NUM_SEQ_INTRP_ANTERIOR,
                LAG(DATA_HORA_FIM_INTRP) OVER (
                    PARTITION BY
                        TRIM(CAST(NUM_UC_UCI AS VARCHAR)),
                        TRIM(CAST(COD_TIPO_INTRP AS VARCHAR)),
                        TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR))
                    ORDER BY DTHR_INICIO_INTRP_UC, DATA_HORA_FIM_INTRP, TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))
                ) AS FIM_ANTERIOR
            FROM gold_apuracao_uc
            WHERE CI_LIQUIDO = 1
        )
        SELECT *
        FROM base
        WHERE FIM_ANTERIOR > DTHR_INICIO_INTRP_UC
        ORDER BY CHI_LIQUIDO DESC NULLS LAST, DURACAO_HORA DESC NULLS LAST
        LIMIT {sample_limit}
    """
    sample_df = query_df(db_path, sample_sql)
    st.dataframe(sample_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Baixar amostra exibida",
        sample_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="amostra_sobreposicao_residual.csv",
        mime="text/csv",
    )


def show_dic_fic(db_path: str) -> None:
    st.subheader("Apuração DIC/FIC")

    if not require_table(db_path, "gold_apuracao_uc"):
        return

    totals_sql = """
        SELECT 'gold_apuracao_uc' AS ORIGEM, COUNT(*) AS LINHAS,
               SUM(CI_LIQUIDO) AS FIC_CI, SUM(CHI_LIQUIDO) AS DIC_CHI
        FROM gold_apuracao_uc
        UNION ALL
        SELECT 'gold_continuidade_uc', COUNT(*), SUM(FIC), SUM(DIC)
        FROM gold_continuidade_uc
        UNION ALL
        SELECT 'gold_apuracao_previa', COUNT(*), SUM(CI_LIQUIDO), SUM(CHI_LIQUIDO)
        FROM gold_apuracao_previa
    """
    totals_df = query_df(db_path, totals_sql)
    st.dataframe(totals_df, use_container_width=True, hide_index=True)

    by_type_sql = """
        SELECT
            COD_TIPO_INTRP,
            COUNT(*) AS LINHAS,
            SUM(CI_LIQUIDO) AS FIC,
            SUM(CHI_LIQUIDO) AS DIC
        FROM gold_apuracao_uc
        GROUP BY COD_TIPO_INTRP
        ORDER BY COD_TIPO_INTRP
    """
    duration_sql = """
        SELECT
            COUNT(*) AS LINHAS,
            MIN(DURACAO_HORA) AS MIN_H,
            QUANTILE_CONT(DURACAO_HORA, 0.50) AS P50_H,
            QUANTILE_CONT(DURACAO_HORA, 0.90) AS P90_H,
            QUANTILE_CONT(DURACAO_HORA, 0.99) AS P99_H,
            MAX(DURACAO_HORA) AS MAX_H
        FROM gold_apuracao_uc
    """

    left, right = st.columns(2)
    left.dataframe(query_df(db_path, by_type_sql), use_container_width=True, hide_index=True)
    right.dataframe(query_df(db_path, duration_sql), use_container_width=True, hide_index=True)


def show_prodist(db_path: str, sample_limit: int) -> None:
    st.subheader("Ressarcimento PRODIST")

    if not require_table(db_path, "gold_ressarcimento_prodist"):
        return

    totals_sql = """
        SELECT
            COUNT(*) AS UCS_AVALIADAS,
            SUM(CASE WHEN COMP_TOTAL_PRODIST > 0 THEN 1 ELSE 0 END) AS UCS_COM_COMPENSACAO,
            SUM(COMP_DIC_PRODIST) AS COMP_DIC,
            SUM(COMP_FIC_PRODIST) AS COMP_FIC,
            SUM(COMP_DMIC_PRODIST) AS COMP_DMIC,
            SUM(COMP_GERAL_CONTINUIDADE_PRODIST) AS COMP_CONTINUIDADE,
            SUM(COMP_DICRI_PRODIST) AS COMP_DICRI,
            SUM(COMP_DISE_PRODIST) AS COMP_DISE,
            SUM(COMP_TOTAL_PRODIST) AS COMP_TOTAL
        FROM gold_ressarcimento_prodist
    """
    totals = query_df(db_path, totals_sql).iloc[0]
    show_metric_cards(
        [
            ("UCs avaliadas", totals["UCS_AVALIADAS"], None),
            ("UCs com compensação", totals["UCS_COM_COMPENSACAO"], None),
            ("Comp. total", totals["COMP_TOTAL"], "R$ estimado"),
        ]
    )
    st.dataframe(pd.DataFrame([totals]), use_container_width=True, hide_index=True)

    tem_causa71 = column_exists(db_path, "gold_ressarcimento_prodist", "CAUSA71")
    tem_dic_brt = column_exists(db_path, "gold_ressarcimento_prodist", "DIC_BRT")
    tem_siglas_iqs = column_exists(db_path, "gold_ressarcimento_prodist", "SIGLAS_TIQS_DIC")
    causa71_select_sql = "CAUSA71," if tem_causa71 else "'N' AS CAUSA71,"
    brutos_select_sql = (
        """
            DIC_BRT,
            FIC_BRT,
            DMIC_BRT,
"""
        if tem_dic_brt
        else """
            NULL AS DIC_BRT,
            NULL AS FIC_BRT,
            NULL AS DMIC_BRT,
"""
    )
    siglas_select_sql = (
        """
            SIGLAS_TIQS_DIC,
            SIGLAS_REID_DIC,
            SIGLAS_TIQS_FIC,
            SIGLAS_REID_FIC,
"""
        if tem_siglas_iqs
        else """
            NULL AS SIGLAS_TIQS_DIC,
            NULL AS SIGLAS_REID_DIC,
            NULL AS SIGLAS_TIQS_FIC,
            NULL AS SIGLAS_REID_FIC,
"""
    )
    causa71_sem_excluidos_sql = (
        "          AND COALESCE(CAUSA71, 'N') = 'N'\n" if tem_causa71 else ""
    )
    causa71_somente_excluidos_sql = (
        "             OR COALESCE(CAUSA71, 'N') = 'S'\n" if tem_causa71 else ""
    )

    ranking_filter = st.selectbox(
        "Filtro do ranking de compensações",
        [
            "Sem eventos excluídos",
            "Todas as UCs",
            "Somente UCs com eventos excluídos",
        ],
        help=(
            "COD_COMP_INTRP=52 e COD_CAUSA_INTRP=71 não compõem DIC/FIC/DMIC "
            "nem a base de compensação. COMP52_CAUSA71 é marcador complementar."
        ),
    )
    if ranking_filter == "Sem eventos excluídos":
        exclusion_filter_sql = """
          AND COALESCE(COMP52, 'N') = 'N'
"""
        exclusion_filter_sql += causa71_sem_excluidos_sql
        exclusion_filter_sql += """
          AND COALESCE(POSTO_PARTICULAR, 'N') = 'N'
          AND COALESCE(CHAVE_PARTICULAR, 'N') = 'N'
          AND COALESCE(UC_ACESSANTE_COMPENSACAO, 'N') = 'N'
        """
    elif ranking_filter == "Somente UCs com eventos excluídos":
        exclusion_filter_sql = """
          AND (
                COALESCE(COMP52, 'N') = 'S'
"""
        exclusion_filter_sql += causa71_somente_excluidos_sql
        exclusion_filter_sql += """
             OR COALESCE(POSTO_PARTICULAR, 'N') = 'S'
             OR COALESCE(CHAVE_PARTICULAR, 'N') = 'S'
             OR COALESCE(UC_ACESSANTE_COMPENSACAO, 'N') = 'S'
          )
        """
    else:
        exclusion_filter_sql = ""

    top_sql = f"""
        SELECT
            UC,
            DIC,
            FIC,
            DMIC,
            {brutos_select_sql}
            DIC_BASE_COMPENSACAO,
            FIC_BASE_COMPENSACAO,
            DMIC_BASE_COMPENSACAO,
            {siglas_select_sql}
            META_DIC,
            META_FIC,
            META_DMIC,
            COMP52,
            {causa71_select_sql}
            POSTO_PARTICULAR,
            CHAVE_PARTICULAR,
            UC_ACESSANTE_COMPENSACAO,
            VRC,
            COMP_TOTAL_PRODIST,
            STATUS_CALCULO_PRODIST
        FROM gold_ressarcimento_prodist
        WHERE COMP_TOTAL_PRODIST > 0
        {exclusion_filter_sql}
        ORDER BY COMP_TOTAL_PRODIST DESC
        LIMIT {sample_limit}
    """
    st.dataframe(query_df(db_path, top_sql), use_container_width=True, hide_index=True)


def show_marts(anomes: str, preview_rows: int) -> None:
    st.subheader("Arquivos Gerados")

    files = sorted(MARTS_DIR.glob(f"*{anomes}*"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        st.info("Nenhum arquivo encontrado em `data/marts` para a competência selecionada.")
        return

    files_df = pd.DataFrame(
        [
            {
                "arquivo": path.name,
                "tamanho_mb": round(path.stat().st_size / 1024 / 1024, 2),
                "alterado_em": pd.Timestamp(path.stat().st_mtime, unit="s"),
            }
            for path in files
        ]
    )
    st.dataframe(files_df, use_container_width=True, hide_index=True)

    selected_name = st.selectbox("Pré-visualizar arquivo", [path.name for path in files])
    selected_path = MARTS_DIR / selected_name

    if selected_path.suffix.upper() == ".TXT":
        st.code(read_text(str(selected_path)))
    elif selected_path.suffix.upper() == ".CSV":
        st.caption(f"Mostrando somente as primeiras {preview_rows} linhas.")
        st.dataframe(read_csv_preview(str(selected_path), preview_rows), use_container_width=True)
    else:
        st.info("Prévia disponível apenas para CSV e TXT.")

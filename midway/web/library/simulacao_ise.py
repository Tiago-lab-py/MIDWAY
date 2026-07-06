from __future__ import annotations

from midway.web.library.shared import *


def show_ise_simulation(db_path: str, sample_limit: int) -> None:
    st.subheader("Simulação de ISE por Janela")
    st.caption(
        "Simula o expurgo de DIC/FIC normal e a transferência para DISE em uma janela de tempestade "
        "por regional. É uma análise de apoio; não altera o DuckDB nem os arquivos IQS."
    )

    required_tables = [
        "gold_apuracao_uc",
        "gold_continuidade_uc",
    ]
    if not all(require_table(db_path, table_name) for table_name in required_tables):
        return

    st.info(
        "Use esta tela para testar janelas ISE antes da aplicação oficial. "
        "A simulação mostra dois cenários: expurgo somente do trecho sobreposto à janela "
        "e expurgo do registro inteiro atingido pela janela."
    )

    regionals_df = query_df(
        db_path,
        """
        SELECT DISTINCT COALESCE(NULLIF(TRIM(CAST(REGIONAL AS VARCHAR)), ''), 'COPEL') AS REGIONAL
        FROM gold_apuracao_uc
        ORDER BY REGIONAL
        """,
    )
    if regionals_df.empty:
        st.warning("Nenhuma regional encontrada em `gold_apuracao_uc`.")
        return

    range_df = query_df(
        db_path,
        """
        SELECT
            MIN(CAST(DATA_HORA_INIC_INTRP AS TIMESTAMP)) AS DATA_MIN,
            MAX(CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) AS DATA_MAX
        FROM gold_apuracao_uc
        WHERE DATA_HORA_INIC_INTRP IS NOT NULL
          AND DATA_HORA_FIM_INTRP IS NOT NULL
        """,
    )
    if range_df.empty or pd.isna(range_df.iloc[0]["DATA_MIN"]) or pd.isna(range_df.iloc[0]["DATA_MAX"]):
        st.warning("Nao ha janela temporal valida em `gold_apuracao_uc`.")
        return

    data_min = pd.Timestamp(range_df.iloc[0]["DATA_MIN"]).to_pydatetime()
    data_max = pd.Timestamp(range_df.iloc[0]["DATA_MAX"]).to_pydatetime()
    default_start = dt.datetime.combine(data_max.date(), dt.time(0, 0))
    default_end = dt.datetime.combine(data_max.date(), dt.time(23, 59))

    regional_options = regionals_df["REGIONAL"].astype(str).tolist()
    left, middle, right = st.columns([1.4, 1, 1])
    with left:
        selected_regionals = st.multiselect(
            "Regionais da janela ISE",
            regional_options,
            default=regional_options[:1],
            help="Selecione uma ou mais regionais afetadas pela tempestade.",
        )
    with middle:
        tipo_ise = st.selectbox(
            "TIPO_PROTOC_JUSTIF_UCI simulado",
            ["5", "6"],
            help="Tipos 5 e 6 sao tratados como ISE/DISE no MIDWAY.",
        )
    with right:
        only_liquid = st.checkbox(
            "Somente DIC/FIC líquido",
            value=True,
            help="Quando marcado, simula expurgo apenas em registros atualmente `TIPO_PROTOC_JUSTIF_UCI = 0`.",
        )

    time_left, time_middle, time_right, time_extra = st.columns([1, 1, 1, 1])
    with time_left:
        start_date = st.date_input(
            "Data início",
            value=default_start.date(),
            min_value=data_min.date(),
            max_value=data_max.date(),
        )
    with time_middle:
        start_time = st.time_input("Hora início", value=default_start.time())
    with time_right:
        end_date = st.date_input(
            "Data fim",
            value=default_end.date(),
            min_value=data_min.date(),
            max_value=data_max.date(),
        )
    with time_extra:
        end_time = st.time_input("Hora fim", value=default_end.time())

    min_overlap_minutes = st.slider(
        "Sobreposição mínima com a janela (minutos)",
        1,
        180,
        1,
        step=1,
        help="Evita considerar registros que encostam na janela por poucos segundos.",
    )

    if not selected_regionals:
        st.warning("Selecione pelo menos uma regional.")
        return

    start_dt = dt.datetime.combine(start_date, start_time)
    end_dt = dt.datetime.combine(end_date, end_time)
    if end_dt <= start_dt:
        st.error("A data/hora final deve ser maior que a data/hora inicial.")
        return

    regionals_sql = ", ".join(sql_literal_for_streamlit(regional) for regional in selected_regionals)
    liquid_filter_sql = ""
    if only_liquid:
        liquid_filter_sql = "AND TRIM(CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'"

    start_sql = sql_literal_for_streamlit(start_dt.strftime("%Y-%m-%d %H:%M:%S"))
    end_sql = sql_literal_for_streamlit(end_dt.strftime("%Y-%m-%d %H:%M:%S"))
    min_overlap_hours = min_overlap_minutes / 60.0

    base_sql = f"""
        WITH params AS (
            SELECT
                CAST({start_sql} AS TIMESTAMP) AS INICIO_ISE,
                CAST({end_sql} AS TIMESTAMP) AS FIM_ISE
        ),
        candidatos AS (
            SELECT
                COALESCE(NULLIF(TRIM(CAST(a.REGIONAL AS VARCHAR)), ''), 'COPEL') AS REGIONAL,
                TRIM(CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                TRIM(CAST(a.NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)) AS UC,
                TRIM(CAST(a.COD_TIPO_INTRP AS VARCHAR)) AS COD_TIPO_INTRP,
                TRIM(CAST(a.TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) AS TIPO_PROTOC_JUSTIF_UCI_ATUAL,
                CAST(a.DATA_HORA_INIC_INTRP AS TIMESTAMP) AS DATA_HORA_INIC_INTRP,
                CAST(a.DATA_HORA_FIM_INTRP AS TIMESTAMP) AS DATA_HORA_FIM_INTRP,
                COALESCE(a.DURACAO_HORA, 0) AS DURACAO_HORA,
                COALESCE(a.CI_LIQUIDO, 0) AS CI_LIQUIDO,
                COALESCE(a.CHI_LIQUIDO, 0) AS CHI_LIQUIDO,
                GREATEST(CAST(a.DATA_HORA_INIC_INTRP AS TIMESTAMP), p.INICIO_ISE) AS INICIO_SOBREPOSTO,
                LEAST(CAST(a.DATA_HORA_FIM_INTRP AS TIMESTAMP), p.FIM_ISE) AS FIM_SOBREPOSTO
            FROM gold_apuracao_uc a
            CROSS JOIN params p
            WHERE a.DATA_HORA_INIC_INTRP IS NOT NULL
              AND a.DATA_HORA_FIM_INTRP IS NOT NULL
              AND NULLIF(TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
              AND COALESCE(NULLIF(TRIM(CAST(a.REGIONAL AS VARCHAR)), ''), 'COPEL') IN ({regionals_sql})
              AND CAST(a.DATA_HORA_INIC_INTRP AS TIMESTAMP) < p.FIM_ISE
              AND CAST(a.DATA_HORA_FIM_INTRP AS TIMESTAMP) > p.INICIO_ISE
              AND COALESCE(a.CI_LIQUIDO, 0) + COALESCE(a.CHI_LIQUIDO, 0) > 0
              {liquid_filter_sql}
        ),
        calculo AS (
            SELECT
                *,
                DATE_DIFF('second', INICIO_SOBREPOSTO, FIM_SOBREPOSTO) / 3600.0 AS HORAS_SOBREPOSTAS
            FROM candidatos
            WHERE FIM_SOBREPOSTO > INICIO_SOBREPOSTO
        )
        SELECT
            REGIONAL,
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            UC,
            COD_TIPO_INTRP,
            TIPO_PROTOC_JUSTIF_UCI_ATUAL,
            '{tipo_ise}' AS TIPO_PROTOC_JUSTIF_UCI_SIMULADO,
            DATA_HORA_INIC_INTRP,
            DATA_HORA_FIM_INTRP,
            INICIO_SOBREPOSTO,
            FIM_SOBREPOSTO,
            DURACAO_HORA,
            CI_LIQUIDO,
            CHI_LIQUIDO,
            HORAS_SOBREPOSTAS,
            LEAST(CHI_LIQUIDO, HORAS_SOBREPOSTAS) AS DIC_EXPURGO_JANELA,
            CASE WHEN HORAS_SOBREPOSTAS > 0 THEN CI_LIQUIDO ELSE 0 END AS FIC_EXPURGO_JANELA,
            CHI_LIQUIDO AS DIC_EXPURGO_REGISTRO,
            CI_LIQUIDO AS FIC_EXPURGO_REGISTRO,
            GREATEST(CHI_LIQUIDO - LEAST(CHI_LIQUIDO, HORAS_SOBREPOSTAS), 0) AS DIC_NORMAL_REMANESCENTE_JANELA,
            CASE
                WHEN HORAS_SOBREPOSTAS >= DURACAO_HORA THEN 0
                ELSE CI_LIQUIDO
            END AS FIC_NORMAL_REMANESCENTE_JANELA
        FROM calculo
        WHERE HORAS_SOBREPOSTAS >= {float(min_overlap_hours)}
    """

    summary_sql = f"""
        SELECT
            REGIONAL,
            COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS OCORRENCIAS,
            COUNT(DISTINCT UC) AS UCS_AFETADAS,
            COUNT(*) AS LINHAS_UC,
            SUM(DIC_EXPURGO_JANELA) AS DISE_SIMULADO_JANELA,
            SUM(FIC_EXPURGO_JANELA) AS FISE_SIMULADO_JANELA,
            SUM(DIC_EXPURGO_REGISTRO) AS DISE_SIMULADO_REGISTRO,
            SUM(FIC_EXPURGO_REGISTRO) AS FISE_SIMULADO_REGISTRO
        FROM ({base_sql}) base
        GROUP BY REGIONAL
        ORDER BY DISE_SIMULADO_REGISTRO DESC, OCORRENCIAS DESC
    """
    summary_df = query_df(db_path, summary_sql)
    if summary_df.empty:
        st.success("Nenhum registro apurável encontrado para a janela ISE informada.")
        return

    totals_sql = f"""
        SELECT
            COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS OCORRENCIAS,
            COUNT(DISTINCT UC) AS UCS_AFETADAS,
            SUM(DIC_EXPURGO_JANELA) AS DISE_SIMULADO_JANELA,
            SUM(DIC_EXPURGO_REGISTRO) AS DISE_SIMULADO_REGISTRO
        FROM ({base_sql}) base
    """
    totals = query_df(db_path, totals_sql).iloc[0]
    show_metric_cards(
        [
            ("Ocorrências", totals["OCORRENCIAS"], "Com sobreposição à janela"),
            ("UCs afetadas", totals["UCS_AFETADAS"], "Distintas no recorte"),
            ("DISE janela", totals["DISE_SIMULADO_JANELA"], "Horas sobrepostas"),
            ("DISE registro", totals["DISE_SIMULADO_REGISTRO"], "Registro inteiro"),
        ]
    )

    st.markdown("### Resumo por regional")
    st.dataframe(
        summary_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "DISE_SIMULADO_JANELA": st.column_config.NumberColumn("DISE janela", format="%.3f"),
            "DISE_SIMULADO_REGISTRO": st.column_config.NumberColumn("DISE registro", format="%.3f"),
        },
    )

    uc_sql = f"""
        WITH sim AS (
            SELECT
                UC,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS OCORRENCIAS_ISE_SIMULADAS,
                SUM(DIC_EXPURGO_JANELA) AS DISE_ADICIONAL_JANELA,
                SUM(FIC_EXPURGO_JANELA) AS FISE_ADICIONAL_JANELA,
                SUM(DIC_EXPURGO_REGISTRO) AS DISE_ADICIONAL_REGISTRO,
                SUM(FIC_EXPURGO_REGISTRO) AS FISE_ADICIONAL_REGISTRO
            FROM ({base_sql}) base
            GROUP BY UC
        )
        SELECT
            s.UC,
            s.OCORRENCIAS_ISE_SIMULADAS,
            c.DIC AS DIC_ATUAL,
            c.FIC AS FIC_ATUAL,
            c.DIC_ISE AS DISE_ATUAL,
            c.FIC_ISE AS FISE_ATUAL,
            c.META_DISE,
            s.DISE_ADICIONAL_JANELA,
            s.FISE_ADICIONAL_JANELA,
            s.DISE_ADICIONAL_REGISTRO,
            s.FISE_ADICIONAL_REGISTRO,
            GREATEST(COALESCE(c.DIC, 0) - COALESCE(s.DISE_ADICIONAL_JANELA, 0), 0) AS DIC_NORMAL_SIM_JANELA,
            COALESCE(c.DIC_ISE, 0) + COALESCE(s.DISE_ADICIONAL_JANELA, 0) AS DISE_SIM_JANELA,
            GREATEST(COALESCE(c.DIC, 0) - COALESCE(s.DISE_ADICIONAL_REGISTRO, 0), 0) AS DIC_NORMAL_SIM_REGISTRO,
            COALESCE(c.DIC_ISE, 0) + COALESCE(s.DISE_ADICIONAL_REGISTRO, 0) AS DISE_SIM_REGISTRO,
            CASE
                WHEN COALESCE(c.META_DISE, 0) > 0
                THEN (COALESCE(c.DIC_ISE, 0) + COALESCE(s.DISE_ADICIONAL_JANELA, 0)) / c.META_DISE * 100
                ELSE NULL
            END AS PCT_META_DISE_SIM_JANELA,
            CASE
                WHEN COALESCE(c.META_DISE, 0) > 0
                THEN (COALESCE(c.DIC_ISE, 0) + COALESCE(s.DISE_ADICIONAL_REGISTRO, 0)) / c.META_DISE * 100
                ELSE NULL
            END AS PCT_META_DISE_SIM_REGISTRO
        FROM sim s
        LEFT JOIN gold_continuidade_uc c
          ON CAST(c.UC AS VARCHAR) = CAST(s.UC AS VARCHAR)
        ORDER BY DISE_SIM_REGISTRO DESC, DISE_SIM_JANELA DESC
        LIMIT {int(sample_limit)}
    """
    uc_df = query_df(db_path, uc_sql)
    st.markdown("### Impacto simulado por UC")
    st.dataframe(
        uc_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PCT_META_DISE_SIM_JANELA": st.column_config.ProgressColumn(
                "% meta DISE janela",
                min_value=0,
                max_value=100,
                format="%.2f%%",
            ),
            "PCT_META_DISE_SIM_REGISTRO": st.column_config.ProgressColumn(
                "% meta DISE registro",
                min_value=0,
                max_value=100,
                format="%.2f%%",
            ),
        },
    )
    st.download_button(
        "Baixar impacto por UC",
        uc_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="simulacao_ise_uc.csv",
        mime="text/csv",
    )

    detail_sql = f"""
        SELECT *
        FROM ({base_sql}) base
        ORDER BY
            DIC_EXPURGO_REGISTRO DESC,
            HORAS_SOBREPOSTAS DESC,
            REGIONAL,
            NUM_OCORRENCIA_ADMS
        LIMIT {int(sample_limit)}
    """
    detail_df = query_df(db_path, detail_sql)
    st.markdown("### Registros UC atingidos pela janela")
    st.dataframe(
        detail_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "HORAS_SOBREPOSTAS": st.column_config.NumberColumn("Horas na janela", format="%.3f"),
            "DIC_EXPURGO_JANELA": st.column_config.NumberColumn("DIC expurgo janela", format="%.3f"),
            "DIC_EXPURGO_REGISTRO": st.column_config.NumberColumn("DIC expurgo registro", format="%.3f"),
        },
    )
    st.download_button(
        "Baixar registros da simulação ISE",
        detail_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="simulacao_ise_registros.csv",
        mime="text/csv",
    )

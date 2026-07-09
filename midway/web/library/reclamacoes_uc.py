from __future__ import annotations

import calendar
import os
from datetime import date

from midway.web.library.shared import *


def _fmt_sql_date(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _anomes_periodo() -> tuple[date, date]:
    anomes = os.getenv("ANOMES", "202606")
    ano = int(anomes[:4])
    mes = int(anomes[4:6])
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, 1), date(ano, mes, ultimo_dia)


def _status_filter_sql(status: str) -> str:
    if status == "Com ocorrência provável":
        return " AND TEM_OCORRENCIA_PROVAVEL = 'S'"
    if status == "Sem ocorrência provável":
        return " AND TEM_OCORRENCIA_PROVAVEL = 'N'"
    if status == "Ocorrência validada pós":
        return " AND VALID_POS_OPERACAO = 'S'"
    if status == "Pendentes pós":
        return " AND COALESCE(VALID_POS_OPERACAO, 'N') <> 'S'"
    return ""


@st.cache_data(show_spinner=False)
def reclamacoes_overview(db_path: str, start_date: date, end_date: date, status: str, min_score: int, uc: str):
    uc_filter = ""
    if uc.strip():
        uc_filter = f" AND TRIM(CAST(UC AS VARCHAR)) = {sql_literal_for_streamlit(uc.strip())}"

    return query_df(
        db_path,
        f"""
        SELECT
            COUNT(*) AS QTD_RECLAMACOES,
            COUNT(DISTINCT UC) AS QTD_UCS,
            COUNT(DISTINCT NUM_OCORRENCIA_ADMS) FILTER (WHERE TEM_OCORRENCIA_PROVAVEL = 'S') AS QTD_OCORRENCIAS_PROVAVEIS,
            SUM(CASE WHEN TEM_OCORRENCIA_PROVAVEL = 'S' THEN 1 ELSE 0 END) AS QTD_COM_OCORRENCIA_PROVAVEL,
            SUM(CASE WHEN TEM_OCORRENCIA_PROVAVEL = 'N' THEN 1 ELSE 0 END) AS QTD_SEM_OCORRENCIA_PROVAVEL,
            SUM(CASE WHEN VALID_POS_OPERACAO = 'S' THEN 1 ELSE 0 END) AS QTD_OCORRENCIA_VALIDADA_POS,
            MAX(SCORE_VINCULO_RECLAMACAO) AS MAX_SCORE_VINCULO
        FROM gold_reclamacao_uc_vinculada
        WHERE CAST(DTHR_RECLAMACAO AS DATE) >= DATE '{_fmt_sql_date(start_date)}'
          AND CAST(DTHR_RECLAMACAO AS DATE) <= DATE '{_fmt_sql_date(end_date)}'
          AND COALESCE(SCORE_VINCULO_RECLAMACAO, 0) >= {int(min_score)}
          {uc_filter}
          {_status_filter_sql(status)}
        """,
    )


@st.cache_data(show_spinner=False)
def reclamacoes_ranking_uc(db_path: str, start_date: date, end_date: date, status: str, min_score: int, sample_limit: int):
    return query_df(
        db_path,
        f"""
        SELECT
            UC,
            COUNT(*) AS QTD_RECLAMACOES,
            COUNT(DISTINCT NUM_OCORRENCIA_ADMS) FILTER (WHERE TEM_OCORRENCIA_PROVAVEL = 'S') AS QTD_OCORRENCIAS_PROVAVEIS,
            SUM(CASE WHEN TEM_OCORRENCIA_PROVAVEL = 'S' THEN 1 ELSE 0 END) AS QTD_COM_OCORRENCIA_PROVAVEL,
            SUM(CASE WHEN TEM_OCORRENCIA_PROVAVEL = 'N' THEN 1 ELSE 0 END) AS QTD_SEM_OCORRENCIA_PROVAVEL,
            SUM(CASE WHEN VALID_POS_OPERACAO = 'S' THEN 1 ELSE 0 END) AS QTD_OCORRENCIA_VALIDADA_POS,
            MAX(SCORE_VINCULO_RECLAMACAO) AS MAX_SCORE_VINCULO,
            MIN(DISTANCIA_MINUTOS) AS MENOR_DISTANCIA_MINUTOS,
            MAX(COALESCE(COMP_TOTAL_PRODIST_UC, 0)) AS COMP_TOTAL_PRODIST_UC_REFERENCIA
        FROM gold_reclamacao_uc_vinculada
        WHERE CAST(DTHR_RECLAMACAO AS DATE) >= DATE '{_fmt_sql_date(start_date)}'
          AND CAST(DTHR_RECLAMACAO AS DATE) <= DATE '{_fmt_sql_date(end_date)}'
          AND COALESCE(SCORE_VINCULO_RECLAMACAO, 0) >= {int(min_score)}
          {_status_filter_sql(status)}
        GROUP BY UC
        ORDER BY
            QTD_SEM_OCORRENCIA_PROVAVEL DESC,
            QTD_RECLAMACOES DESC,
            MAX_SCORE_VINCULO DESC,
            COMP_TOTAL_PRODIST_UC_REFERENCIA DESC
        LIMIT {int(sample_limit)}
        """,
    )


@st.cache_data(show_spinner=False)
def reclamacoes_ranking_ocorrencia(db_path: str, start_date: date, end_date: date, status: str, min_score: int, sample_limit: int):
    return query_df(
        db_path,
        f"""
        SELECT
            NUM_OCORRENCIA_ADMS,
            COUNT(*) AS QTD_RECLAMACOES,
            COUNT(DISTINCT UC) AS QTD_UCS_RECLAMANTES,
            MAX(UCS_APURAVEIS_OCORRENCIA) AS UCS_APURAVEIS_OCORRENCIA,
            MAX(VALID_POS_OPERACAO) AS VALID_POS_OPERACAO,
            MAX(SCORE_VINCULO_RECLAMACAO) AS MAX_SCORE_VINCULO,
            MIN(DISTANCIA_MINUTOS) AS MENOR_DISTANCIA_MINUTOS,
            STRING_AGG(DISTINCT TIPO_RECLAMACAO_PROVAVEL, ', ' ORDER BY TIPO_RECLAMACAO_PROVAVEL) AS TIPOS_RECLAMACAO_PROVAVEIS,
            STRING_AGG(DISTINCT CAUSA_PROVAVEL_RECLAMACAO, ', ' ORDER BY CAUSA_PROVAVEL_RECLAMACAO) AS CAUSAS_PROVAVEIS_RECLAMACAO,
            STRING_AGG(DISTINCT PREVIA_CAUSA_RECLAMACAO, ', ' ORDER BY PREVIA_CAUSA_RECLAMACAO) AS PREVIAS_CAUSA_RECLAMACAO,
            STRING_AGG(DISTINCT GRUPO_CAUSA_IQS, ', ' ORDER BY GRUPO_CAUSA_IQS) AS GRUPOS_CAUSA_IQS,
            STRING_AGG(DISTINCT GRUPO_COMPONENTE_IQS, ', ' ORDER BY GRUPO_COMPONENTE_IQS) AS GRUPOS_COMPONENTE_IQS,
            SUM(CASE WHEN ADERENCIA_RECLAMACAO_CAUSA_IQS = 'ALTA' THEN 1 ELSE 0 END) AS QTD_ADERENCIA_ALTA,
            SUM(CASE WHEN ADERENCIA_RECLAMACAO_CAUSA_IQS = 'MEDIA' THEN 1 ELSE 0 END) AS QTD_ADERENCIA_MEDIA,
            MAX(DIC_OCORRENCIA) AS DIC_OCORRENCIA,
            MAX(FIC_OCORRENCIA) AS FIC_OCORRENCIA
        FROM gold_reclamacao_uc_vinculada
        WHERE CAST(DTHR_RECLAMACAO AS DATE) >= DATE '{_fmt_sql_date(start_date)}'
          AND CAST(DTHR_RECLAMACAO AS DATE) <= DATE '{_fmt_sql_date(end_date)}'
          AND COALESCE(SCORE_VINCULO_RECLAMACAO, 0) >= {int(min_score)}
          AND TEM_OCORRENCIA_PROVAVEL = 'S'
          AND NUM_OCORRENCIA_ADMS IS NOT NULL
          {_status_filter_sql(status)}
        GROUP BY NUM_OCORRENCIA_ADMS
        ORDER BY
            QTD_RECLAMACOES DESC,
            QTD_UCS_RECLAMANTES DESC,
            MAX_SCORE_VINCULO DESC,
            DIC_OCORRENCIA DESC
        LIMIT {int(sample_limit)}
        """,
    )


@st.cache_data(show_spinner=False)
def reclamacoes_detalhe(db_path: str, start_date: date, end_date: date, status: str, min_score: int, sample_limit: int, uc: str):
    uc_filter = ""
    if uc.strip():
        uc_filter = f" AND TRIM(CAST(UC AS VARCHAR)) = {sql_literal_for_streamlit(uc.strip())}"

    return query_df(
        db_path,
        f"""
        SELECT
            ID_RECLAMACAO,
            UC,
            DTHR_RECLAMACAO,
            TIPO_RECLAMACAO_PROVAVEL,
            CAUSA_PROVAVEL_RECLAMACAO,
            PREVIA_CAUSA_RECLAMACAO,
            ADERENCIA_RECLAMACAO_CAUSA_IQS,
            DESC_CAUSA_INTRP,
            DESC_COMP_INTRP,
            GRUPO_CAUSA_IQS,
            GRUPO_COMPONENTE_IQS,
            STATUS_AVALIACAO_RECLAMACAO,
            CLASSIFICACAO_VINCULO_RECLAMACAO,
            SCORE_VINCULO_RECLAMACAO,
            DISTANCIA_MINUTOS,
            POSICAO_RECLAMACAO,
            VALID_POS_OPERACAO,
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            NUM_INTRP_UCI,
            CONJUNTO,
            ALIM_INTRP,
            NUM_OPER_CHV_INTRP,
            NUM_GEO_CHV_INTRP,
            INICIO_INTERRUPCAO_UC,
            FIM_INTERRUPCAO,
            DURACAO_HORA,
            CI_LIQUIDO,
            CHI_LIQUIDO,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            TEXTO_RECLAMACAO,
            TEXTO_RETORNO,
            UCS_APURAVEIS_OCORRENCIA,
            FIC_OCORRENCIA,
            DIC_OCORRENCIA,
            COMP_TOTAL_PRODIST_UC
        FROM gold_reclamacao_uc_vinculada
        WHERE CAST(DTHR_RECLAMACAO AS DATE) >= DATE '{_fmt_sql_date(start_date)}'
          AND CAST(DTHR_RECLAMACAO AS DATE) <= DATE '{_fmt_sql_date(end_date)}'
          AND COALESCE(SCORE_VINCULO_RECLAMACAO, 0) >= {int(min_score)}
          {uc_filter}
          {_status_filter_sql(status)}
        ORDER BY
            DTHR_RECLAMACAO DESC,
            SCORE_VINCULO_RECLAMACAO DESC,
            DISTANCIA_MINUTOS ASC
        LIMIT {int(sample_limit)}
        """,
    )


def show_reclamacoes_uc(db_path: str, sample_limit: int) -> None:
    st.subheader("Reclamações UC")
    st.caption(
        "Avalia reclamações do DBGUO vinculadas às interrupções prováveis por UC, horário e ocorrência. "
        "A tela lê tabelas gold para manter o painel rápido."
    )

    required_tables = ["gold_reclamacao_uc_vinculada", "gold_reclamacao_uc_resumo"]
    if not all(require_table(db_path, table_name) for table_name in required_tables):
        st.info(
            "Execute `run.bat dbguo_reclamacoes` para gerar "
            "`gold_reclamacao_uc_vinculada` e `gold_reclamacao_uc_resumo`."
        )
        return

    periodo_inicio, periodo_fim = _anomes_periodo()

    col_uc, col_inicio, col_fim = st.columns([1, 1, 1])
    with col_uc:
        uc = st.text_input("UC específica", value="", placeholder="Opcional")
    with col_inicio:
        start_date = st.date_input("Data inicial reclamação", value=periodo_inicio)
    with col_fim:
        end_date = st.date_input("Data final reclamação", value=periodo_fim)

    col_status, col_score = st.columns([2, 1])
    with col_status:
        status = st.selectbox(
            "Filtro de vínculo",
            [
                "Todos",
                "Com ocorrência provável",
                "Sem ocorrência provável",
                "Pendentes pós",
                "Ocorrência validada pós",
            ],
        )
    with col_score:
        min_score = st.slider("Score mínimo vínculo", 0, 100, 0, step=5)

    overview_df = reclamacoes_overview(db_path, start_date, end_date, status, min_score, uc)
    if overview_df.empty:
        st.success("Nenhuma reclamação encontrada para os filtros informados.")
        return

    overview = overview_df.iloc[0]
    show_metric_cards(
        [
            ("Reclamações", overview["QTD_RECLAMACOES"], "No filtro"),
            ("UCs", overview["QTD_UCS"], "Com reclamação"),
            ("Com vínculo", overview["QTD_COM_OCORRENCIA_PROVAVEL"], "Ocorrência provável"),
            ("Sem vínculo", overview["QTD_SEM_OCORRENCIA_PROVAVEL"], "Sem ocorrência provável"),
        ]
    )

    if not uc.strip():
        st.markdown("### Ranking de UCs com reclamações")
        ranking_df = reclamacoes_ranking_uc(db_path, start_date, end_date, status, min_score, sample_limit)
        if ranking_df.empty:
            st.success("Nenhuma UC encontrada para os filtros informados.")
        else:
            st.dataframe(
                ranking_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "MAX_SCORE_VINCULO": st.column_config.ProgressColumn("Max score", min_value=0, max_value=100),
                    "COMP_TOTAL_PRODIST_UC_REFERENCIA": st.column_config.NumberColumn("Comp. referência", format="%.2f"),
                },
            )
            st.download_button(
                "Baixar ranking de UCs",
                ranking_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name="ranking_reclamacoes_uc.csv",
                mime="text/csv",
            )

        st.markdown("### Ranking de ocorrências com reclamações")
        ocorrencia_df = reclamacoes_ranking_ocorrencia(
            db_path,
            start_date,
            end_date,
            status,
            min_score,
            sample_limit,
        )
        if ocorrencia_df.empty:
            st.success("Nenhuma ocorrência encontrada para os filtros informados.")
        else:
            st.dataframe(
                ocorrencia_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "MAX_SCORE_VINCULO": st.column_config.ProgressColumn("Max score", min_value=0, max_value=100),
                    "DIC_OCORRENCIA": st.column_config.NumberColumn("DIC ocorrência", format="%.3f"),
                    "FIC_OCORRENCIA": st.column_config.NumberColumn("FIC ocorrência", format="%.3f"),
                },
            )
            st.download_button(
                "Baixar ranking de ocorrências",
                ocorrencia_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name="ranking_reclamacoes_ocorrencia.csv",
                mime="text/csv",
            )

    st.markdown("### Detalhe das reclamações")
    detalhe_df = reclamacoes_detalhe(db_path, start_date, end_date, status, min_score, sample_limit, uc)
    if detalhe_df.empty:
        st.success("Nenhum detalhe encontrado para os filtros informados.")
        return

    st.dataframe(
        detalhe_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SCORE_VINCULO_RECLAMACAO": st.column_config.ProgressColumn("Score vínculo", min_value=0, max_value=100),
            "DISTANCIA_MINUTOS": st.column_config.NumberColumn("Distância min", format="%.0f"),
            "COMP_TOTAL_PRODIST_UC": st.column_config.NumberColumn("Comp. UC", format="%.2f"),
            "DURACAO_HORA": st.column_config.NumberColumn("Duração h", format="%.3f"),
            "CHI_LIQUIDO": st.column_config.NumberColumn("DIC linha", format="%.3f"),
        },
    )
    st.download_button(
        "Baixar detalhe de reclamações",
        detalhe_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="detalhe_reclamacoes_uc.csv",
        mime="text/csv",
    )

from __future__ import annotations

from midway.web.library.shared import *


def show_validacao_pos_operacao(db_path: str, sample_limit: int) -> None:
    st.subheader("Validação Pós-Operação")
    st.caption(
        "Concentra os registros candidatos à decisão da pós-operação. "
        "A linha 6.2.0 também adiciona apoio à leitura de reclamações DBGUO por ocorrência."
    )

    if not require_table(db_path, "gold_apuracao_uc"):
        return

    status_column = (
        "VALID_POS_OPERACAO"
        if column_exists(db_path, "gold_apuracao_uc", "VALID_POS_OPERACAO")
        else "INDIC_SIT_PROCES_INDIC_UCI"
    )

    resumo_sql = f"""
        SELECT
            COALESCE(NULLIF(TRIM(CAST({status_column} AS VARCHAR)), ''), 'N/I') AS STATUS_POS_OPERACAO,
            COUNT(*) AS LINHAS_UC,
            COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS OCORRENCIAS,
            COUNT(DISTINCT NUM_UC_UCI) AS UCS,
            SUM(CI_LIQUIDO) AS FIC_LIQUIDO,
            SUM(CHI_LIQUIDO) AS DIC_LIQUIDO,
            MAX(DURACAO_HORA) AS MAX_DURACAO_H
        FROM gold_apuracao_uc
        GROUP BY 1
        ORDER BY LINHAS_UC DESC
    """
    st.dataframe(query_df(db_path, resumo_sql), use_container_width=True, hide_index=True)

    detalhe_sql = f"""
        SELECT
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            COD_CONJTO_ELET_ANEEL_INTRP,
            REGIONAL,
            {status_column} AS STATUS_POS_OPERACAO,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_TIPO_INTRP,
            COUNT(*) AS LINHAS_UC,
            COUNT(DISTINCT NUM_UC_UCI) AS UCS,
            SUM(CI_LIQUIDO) AS FIC_LIQUIDO,
            SUM(CHI_LIQUIDO) AS DIC_LIQUIDO,
            MAX(DURACAO_HORA) AS MAX_DURACAO_H
        FROM gold_apuracao_uc
        GROUP BY
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            COD_CONJTO_ELET_ANEEL_INTRP,
            REGIONAL,
            {status_column},
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            COD_TIPO_INTRP
        ORDER BY DIC_LIQUIDO DESC, UCS DESC
        LIMIT {int(sample_limit)}
    """
    st.markdown("### Ocorrências para conferência")
    st.dataframe(query_df(db_path, detalhe_sql), use_container_width=True, hide_index=True)

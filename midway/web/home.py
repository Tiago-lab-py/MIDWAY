from __future__ import annotations

import streamlit as st

from midway.web.library.shared import configure_page, render_header


def main() -> None:
    configure_page()
    render_header()

    st.markdown(
        """
        ### Consolidação Operacional 6.1.0

        Use o menu lateral do Streamlit para navegar pelas páginas do MIDWAY.

        - **01 Conferência ETL**: qualidade, sobreposição, DIC/FIC, ressarcimento e arquivos.
        - **02 Analytics Pós-Operação**: ranking de ocorrências e impacto por conjunto.
        - **03 Dia Crítico**: verificação por conjunto com meta sintética.
        - **04 Simulação ISE**: simulação de janela regional de expurgo.
        - **05 Validação Pós-Operação**: visão inicial para decisões operacionais.
        - **06 Executivo**: resumo gerencial de impacto e compensação estimada.
        - **07 SQL**: catálogo e consulta somente leitura no DuckDB processado.
        """
    )

    st.info(
        "Arquitetura: Oracle IQS/ADMS → DuckDB raw/silver/gold/marts → Streamlit → CSV/relatórios/evidências."
    )


if __name__ == "__main__":
    main()

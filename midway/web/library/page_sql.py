from __future__ import annotations

from midway.web.library.shared import *


def show_sql(db_path: str, sample_limit: int) -> None:
    st.subheader("Consulta SQL Somente Leitura")
    st.caption("Use para consultas rápidas no DuckDB processado. Evite `SELECT *` sem `LIMIT`.")

    tables_df = list_tables(db_path)
    if tables_df.empty:
        st.warning("Nenhuma tabela encontrada no DuckDB processado.")
        return

    with st.expander("Catálogo de tabelas", expanded=True):
        name_filter = st.text_input(
            "Filtrar tabela",
            value="",
            placeholder="Ex.: gold, silver, ressarcimento, sobreposicao",
        )
        filtered_tables = tables_df
        if name_filter.strip():
            filtered_tables = tables_df[
                tables_df["TABELA"].str.contains(name_filter.strip(), case=False, na=False)
            ]

        st.dataframe(
            filtered_tables,
            use_container_width=True,
            hide_index=True,
            column_config={
                "LINHAS": st.column_config.NumberColumn("LINHAS", format="%d"),
                "COLUNAS": st.column_config.NumberColumn("COLUNAS", format="%d"),
            },
        )

    selected_table = st.selectbox(
        "Tabela para consultar",
        filtered_tables["TABELA"].tolist() if not filtered_tables.empty else tables_df["TABELA"].tolist(),
        index=0,
    )
    selected_info = tables_df[tables_df["TABELA"] == selected_table].iloc[0]
    show_metric_cards(
        [
            ("Linhas", selected_info["LINHAS"], "Quantidade de registros na tabela"),
            ("Colunas", selected_info["COLUNAS"], "Quantidade de campos"),
            ("Tipo", selected_info["TIPO"], "Tipo informado pelo DuckDB"),
        ]
    )

    schema_df = table_schema(db_path, selected_table)
    preview_tab, schema_tab, numeric_tab = st.tabs(["Prévia", "Colunas", "Resumo Numérico"])
    with preview_tab:
        st.dataframe(
            table_preview(db_path, selected_table, min(sample_limit, 500)),
            use_container_width=True,
            hide_index=True,
        )
    with schema_tab:
        st.dataframe(schema_df, use_container_width=True, hide_index=True)
    with numeric_tab:
        numeric_df = table_numeric_summary(db_path, selected_table)
        if numeric_df.empty:
            st.info("Tabela sem colunas numéricas para resumir.")
        else:
            st.caption("Resumo limitado às primeiras 20 colunas numéricas.")
            st.dataframe(numeric_df, use_container_width=True, hide_index=True)

    default_sql = f"""
SELECT *
FROM {quote_identifier(selected_table)}
LIMIT {sample_limit}
""".strip()
    sql = st.text_area("SQL", default_sql, height=180, key=f"sql_editor_{selected_table}")

    if st.button("Executar consulta"):
        lowered = sql.strip().lower()
        blocked = ("insert", "update", "delete", "drop", "create", "alter", "attach", "detach", "copy")
        if any(token in lowered.split() for token in blocked):
            st.error("Somente consultas de leitura são permitidas pelo painel.")
            return

        try:
            st.dataframe(query_df(db_path, sql), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"Erro na consulta: {exc}")

from __future__ import annotations

import duckdb
import pandas as pd

from midway.web.library.shared import *


def _quote_relation(relation_name: str) -> str:
    return ".".join(quote_identifier(part) for part in str(relation_name).split("."))


def _resolve_relation(con, database_name: str, schema_name: str, table_name: str) -> str:
    candidates = [
        table_name,
        f"{database_name}.{table_name}",
        f"{database_name}.{schema_name}.{table_name}",
    ]

    last_error = None
    for candidate in candidates:
        try:
            con.execute(f"SELECT COUNT(*) FROM {_quote_relation(candidate)}").fetchone()
            return candidate
        except duckdb.Error as exc:
            last_error = exc

    raise last_error or RuntimeError(f"Tabela nao resolvida: {database_name}.{schema_name}.{table_name}")


@st.cache_data(show_spinner=False)
def sql_page_tables(db_path: str) -> pd.DataFrame:
    sql = """
        SELECT
            table_catalog AS BANCO,
            table_schema AS ESQUEMA,
            table_name AS TABELA,
            table_type AS TIPO
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_catalog, table_name
    """

    rows = []
    with duckdb.connect(db_path, read_only=True) as con:
        tables = con.execute(sql).fetchdf()
        for _, table in tables.iterrows():
            table_name = str(table["TABELA"])
            database_name = str(table["BANCO"])
            schema_name = str(table["ESQUEMA"])
            relation_name = _resolve_relation(con, database_name, schema_name, table_name)
            quoted_relation = _quote_relation(relation_name)
            row_count = con.execute(f"SELECT COUNT(*) FROM {quoted_relation}").fetchone()[0]
            column_count = len(con.execute(f"DESCRIBE {quoted_relation}").fetchdf())
            rows.append(
                {
                    "TABELA": table_name,
                    "NOME_SQL": relation_name,
                    "BANCO": database_name,
                    "ESQUEMA": schema_name,
                    "TIPO": table["TIPO"],
                    "LINHAS": row_count,
                    "COLUNAS": column_count,
                }
            )

    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def sql_page_schema(db_path: str, relation_name: str) -> pd.DataFrame:
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(f"DESCRIBE {_quote_relation(relation_name)}").fetchdf()


@st.cache_data(show_spinner=False)
def sql_page_preview(db_path: str, relation_name: str, rows: int) -> pd.DataFrame:
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(f"SELECT * FROM {_quote_relation(relation_name)} LIMIT {int(rows)}").fetchdf()


@st.cache_data(show_spinner=False)
def sql_page_numeric_summary(db_path: str, relation_name: str) -> pd.DataFrame:
    schema = sql_page_schema(db_path, relation_name)
    numeric_types = ("INTEGER", "BIGINT", "HUGEINT", "DOUBLE", "FLOAT", "REAL", "DECIMAL", "UBIGINT", "UINTEGER")
    numeric_columns = [
        row["column_name"]
        for _, row in schema.iterrows()
        if any(str(row["column_type"]).upper().startswith(numeric_type) for numeric_type in numeric_types)
    ]

    if not numeric_columns:
        return pd.DataFrame()

    quoted_relation = _quote_relation(relation_name)
    expressions = []
    for column in numeric_columns[:20]:
        quoted_column = quote_identifier(column)
        expressions.append(
            f"""
            SELECT
                {sql_literal_for_streamlit(column)} AS COLUNA,
                COUNT({quoted_column}) AS QTD_NAO_NULO,
                MIN({quoted_column}) AS MINIMO,
                MAX({quoted_column}) AS MAXIMO,
                AVG({quoted_column}) AS MEDIA,
                SUM({quoted_column}) AS SOMA
            FROM {quoted_relation}
            """
        )

    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute("\nUNION ALL\n".join(expressions)).fetchdf()


def show_sql(db_path: str, sample_limit: int) -> None:
    st.subheader("Consulta SQL Somente Leitura")
    st.caption("Use para consultas rápidas no DuckDB processado. Evite `SELECT *` sem `LIMIT`.")

    tables_df = sql_page_tables(db_path)
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
            filtro = name_filter.strip()
            filtered_tables = tables_df[
                tables_df["TABELA"].str.contains(filtro, case=False, na=False)
                | tables_df["NOME_SQL"].str.contains(filtro, case=False, na=False)
                | tables_df["BANCO"].str.contains(filtro, case=False, na=False)
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

    selection_df = filtered_tables if not filtered_tables.empty else tables_df
    options = selection_df["NOME_SQL"].tolist()
    labels = {
        row["NOME_SQL"]: (
            row["TABELA"] if row["NOME_SQL"] == row["TABELA"] else f"{row['TABELA']} ({row['BANCO']})"
        )
        for _, row in selection_df.iterrows()
    }

    selected_table = st.selectbox(
        "Tabela para consultar",
        options,
        index=0,
        format_func=lambda value: labels.get(value, value),
    )
    selected_info = tables_df[tables_df["NOME_SQL"] == selected_table].iloc[0]
    show_metric_cards(
        [
            ("Linhas", selected_info["LINHAS"], "Quantidade de registros na tabela"),
            ("Colunas", selected_info["COLUNAS"], "Quantidade de campos"),
            ("Tipo", selected_info["TIPO"], "Tipo informado pelo DuckDB"),
        ]
    )

    schema_df = sql_page_schema(db_path, selected_table)
    preview_tab, schema_tab, numeric_tab = st.tabs(["Prévia", "Colunas", "Resumo Numérico"])
    with preview_tab:
        st.dataframe(
            sql_page_preview(db_path, selected_table, min(sample_limit, 500)),
            use_container_width=True,
            hide_index=True,
        )
    with schema_tab:
        st.dataframe(schema_df, use_container_width=True, hide_index=True)
    with numeric_tab:
        numeric_df = sql_page_numeric_summary(db_path, selected_table)
        if numeric_df.empty:
            st.info("Tabela sem colunas numéricas para resumir.")
        else:
            st.caption("Resumo limitado às primeiras 20 colunas numéricas.")
            st.dataframe(numeric_df, use_container_width=True, hide_index=True)

    default_sql = f"""
SELECT *
FROM {_quote_relation(selected_table)}
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

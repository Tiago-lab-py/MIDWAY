from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from midway.db.postgres import create_postgres_engine, get_config, validate_postgres
from midway.web.library.shared import *


def _read_sql_view(view_name: str, limit: int = 300) -> pd.DataFrame:
    config = get_config()
    engine = create_postgres_engine(config)
    schema = config.schema
    if not schema.replace("_", "").isalnum() or not view_name.replace("_", "").isalnum():
        raise ValueError("View invalida.")
    with engine.connect() as con:
        rows = con.execute(
            text(f"SELECT * FROM {schema}.{view_name} LIMIT :limit"),
            {"limit": limit},
        ).mappings().all()
    return pd.DataFrame([dict(row) for row in rows])


def _sql_scripts() -> pd.DataFrame:
    scripts = []
    for path in sorted(Path("SQL/postgres/ddcq").glob("*.sql")):
        scripts.append(
            {
                "ARQUIVO": path.name,
                "CAMINHO": str(path).replace("\\", "/"),
                "TAMANHO_BYTES": path.stat().st_size,
            }
        )
    return pd.DataFrame(scripts)


def show_governanca(sample_limit: int = 300) -> None:
    st.info(
        "Página Streamlit de transição. O login, perfis e ações sensíveis ficam no frontend React + FastAPI."
    )

    tabs = st.tabs(["Verificação", "SQL Versionado", "Usuários", "Alterações", "Auditoria"])

    with tabs[0]:
        st.subheader("Verificação PostgreSQL")
        try:
            result = validate_postgres()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Status", "OK" if result.ok else "Atenção")
            col2.metric("Tabelas", result.table_count)
            col3.metric("Views", result.view_count)
            col4.metric("Parâmetros", result.parameter_count)

            if result.missing_tables:
                st.warning(f"Tabelas ausentes: {', '.join(result.missing_tables)}")
            if result.missing_views:
                st.warning(f"Views ausentes: {', '.join(result.missing_views)}")
            if result.missing_parameters:
                st.warning(f"Parâmetros ausentes: {', '.join(result.missing_parameters)}")
        except Exception as error:
            st.error(f"Falha ao validar PostgreSQL: {error}")

    with tabs[1]:
        st.subheader("Scripts SQL versionados")
        st.dataframe(_sql_scripts(), use_container_width=True, hide_index=True)
        st.caption("Execução deve ser feita por comando versionado, DBeaver controlado ou processo aprovado.")

    with tabs[2]:
        st.subheader("Usuários e perfis")
        try:
            st.dataframe(
                _read_sql_view("vw_midway_governanca_usuarios", sample_limit),
                use_container_width=True,
                hide_index=True,
            )
        except Exception as error:
            st.error(f"Falha ao consultar usuários: {error}")

    with tabs[3]:
        st.subheader("Registro de alterações")
        try:
            st.dataframe(
                _read_sql_view("vw_midway_governanca_alteracoes", sample_limit),
                use_container_width=True,
                hide_index=True,
            )
        except Exception as error:
            st.error(f"Falha ao consultar alterações: {error}")

    with tabs[4]:
        st.subheader("Auditoria")
        try:
            st.dataframe(
                _read_sql_view("vw_midway_governanca_auditoria", sample_limit),
                use_container_width=True,
                hide_index=True,
            )
        except Exception as error:
            st.error(f"Falha ao consultar auditoria: {error}")

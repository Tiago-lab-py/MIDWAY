from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from midway import __version__


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
MARTS_DIR = DATA_DIR / "marts"
PROCESSED_DIR = DATA_DIR / "processed"
DEFAULT_ANOMES = os.getenv("ANOMES", "202606")


def configure_page(title: str = "MIDWAY - Qualidade ADMS/IQS") -> None:
    st.set_page_config(
        page_title=title,
        page_icon="⚡",
        layout="wide",
    )


def render_header(title: str = "⚡ MIDWAY - Painel de Qualidade ADMS/IQS") -> None:
    st.title(title)
    st.caption(f"Versão {__version__}")


def render_sidebar(*, include_preview_rows: bool = False):
    with st.sidebar:
        st.header("Configuração")
        st.caption(f"MIDWAY {__version__}")
        anomes = st.text_input("ANOMES", value=DEFAULT_ANOMES)
        db_path = processed_path(anomes)
        st.caption(f"DuckDB: `{db_path}`")
        sample_limit = st.slider("Linhas de amostra", 50, 5000, 500, step=50)
        preview_rows = None
        if include_preview_rows:
            preview_rows = st.slider("Linhas de prévia CSV", 20, 1000, 100, step=20)
        refresh = st.button("Limpar cache")

    if refresh:
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    if not db_path.exists():
        st.error(f"DuckDB processado não encontrado: `{db_path}`")
        st.stop()

    return anomes, db_path, sample_limit, preview_rows


def processed_path(anomes: str) -> Path:
    return PROCESSED_DIR / f"iqs_adms_processed_{anomes}.duckdb"


def format_number(value, decimals: int = 2) -> str:
    if value is None:
        return "-"

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if abs(number - round(number)) < 0.000001:
        return f"{int(round(number)):,}".replace(",", ".")

    formatted = f"{number:,.{decimals}f}"
    return formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def latest_file(pattern: str) -> Path | None:
    files = sorted(MARTS_DIR.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


@st.cache_resource(show_spinner=False)
def connect_duckdb(db_path: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(db_path, read_only=True)


@st.cache_data(show_spinner=False)
def query_df(db_path: str, sql: str) -> pd.DataFrame:
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(sql).fetchdf()


def quote_identifier(identifier: str) -> str:
    return '"' + str(identifier).replace('"', '""') + '"'


@st.cache_data(show_spinner=False)
def table_exists(db_path: str, table_name: str) -> bool:
    sql = """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE lower(table_name) = lower(?)
    """
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(sql, [table_name]).fetchone()[0] > 0


@st.cache_data(show_spinner=False)
def column_exists(db_path: str, table_name: str, column_name: str) -> bool:
    sql = """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE lower(table_name) = lower(?)
          AND lower(column_name) = lower(?)
    """
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(sql, [table_name, column_name]).fetchone()[0] > 0


@st.cache_data(show_spinner=False)
def list_tables(db_path: str) -> pd.DataFrame:
    sql = """
        SELECT
            table_name AS TABELA,
            table_type AS TIPO
        FROM information_schema.tables
        WHERE table_schema = 'main'
        ORDER BY table_name
    """
    with duckdb.connect(db_path, read_only=True) as con:
        tables = con.execute(sql).fetchdf()
        rows = []
        for table_name in tables["TABELA"].tolist():
            quoted_table = quote_identifier(table_name)
            row_count = con.execute(f"SELECT COUNT(*) FROM {quoted_table}").fetchone()[0]
            column_count = con.execute(f"SELECT COUNT(*) FROM pragma_table_info('{table_name}')").fetchone()[0]
            rows.append(
                {
                    "TABELA": table_name,
                    "TIPO": tables.loc[tables["TABELA"] == table_name, "TIPO"].iloc[0],
                    "LINHAS": row_count,
                    "COLUNAS": column_count,
                }
            )
        return pd.DataFrame(rows)


@st.cache_data(show_spinner=False)
def table_schema(db_path: str, table_name: str) -> pd.DataFrame:
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(f"PRAGMA table_info('{table_name}')").fetchdf()


@st.cache_data(show_spinner=False)
def table_preview(db_path: str, table_name: str, rows: int) -> pd.DataFrame:
    quoted_table = quote_identifier(table_name)
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(f"SELECT * FROM {quoted_table} LIMIT {int(rows)}").fetchdf()


@st.cache_data(show_spinner=False)
def table_numeric_summary(db_path: str, table_name: str) -> pd.DataFrame:
    schema = table_schema(db_path, table_name)
    numeric_types = ("INTEGER", "BIGINT", "HUGEINT", "DOUBLE", "FLOAT", "REAL", "DECIMAL", "UBIGINT", "UINTEGER")
    numeric_columns = [
        row["name"]
        for _, row in schema.iterrows()
        if any(str(row["type"]).upper().startswith(numeric_type) for numeric_type in numeric_types)
    ]

    if not numeric_columns:
        return pd.DataFrame()

    quoted_table = quote_identifier(table_name)
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
            FROM {quoted_table}
            """
        )
    sql = "\nUNION ALL\n".join(expressions)
    with duckdb.connect(db_path, read_only=True) as con:
        return con.execute(sql).fetchdf()


@st.cache_data(show_spinner=False)
def analytics_overview(db_path: str) -> pd.DataFrame:
    sql = """
        WITH apuracao AS (
            SELECT
                COUNT(*) AS LINHAS_APURAVEIS,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS OCORRENCIAS_APURAVEIS,
                COUNT(DISTINCT NUM_UC_UCI) AS UCS_APURAVEIS,
                SUM(CI_LIQUIDO) AS FIC_TOTAL,
                SUM(CHI_LIQUIDO) AS DIC_TOTAL,
                SUM(CASE WHEN DURACAO_HORA >= 24 THEN 1 ELSE 0 END) AS LINHAS_DURACAO_GE_24H,
                MAX(DURACAO_HORA) AS MAX_DURACAO_H
            FROM gold_apuracao_uc
        ),
        sem_uc AS (
            SELECT
                COUNT(*) AS OCORRENCIAS_COM_INTERRUPCAO_SEM_UC,
                SUM(CASE WHEN OCORRENCIA_SEM_UC_APURAVEL = 'SIM' THEN 1 ELSE 0 END) AS OCORRENCIAS_SEM_UC_COMPLETAS
            FROM gold_ocorrencia_sem_uc
        ),
        ressarcimento AS (
            SELECT
                SUM(CASE WHEN COMP_TOTAL_PRODIST > 0 THEN 1 ELSE 0 END) AS UCS_COM_COMPENSACAO,
                SUM(COMP_TOTAL_PRODIST) AS COMP_TOTAL_PRODIST
            FROM gold_ressarcimento_prodist
        )
        SELECT *
        FROM apuracao
        CROSS JOIN sem_uc
        CROSS JOIN ressarcimento
    """
    return query_df(db_path, sql)


@st.cache_data(show_spinner=False)
def analytics_occurrences(db_path: str, min_score: int, limit: int) -> pd.DataFrame:
    valid_pos_expression = (
        """
        MAX(
            CASE
                WHEN UPPER(TRIM(CAST(COALESCE(VALID_POS_OPERACAO, 'N') AS VARCHAR))) = 'S'
                    THEN 'S'
                ELSE 'N'
            END
        )
        """
        if column_exists(db_path, "gold_apuracao_uc", "VALID_POS_OPERACAO")
        else "'N'"
    )
    sql = f"""
        WITH ocorrencia_apuracao AS (
            SELECT
                COALESCE(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), 'SEM_OCORRENCIA') AS NUM_OCORRENCIA_ADMS,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_OCORRENCIA,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_OCORRENCIA,
                COUNT(*) AS LINHAS_UC,
                COUNT(DISTINCT TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))) AS QTD_INTERRUPCOES,
                COUNT(DISTINCT TRIM(CAST(NUM_UC_UCI AS VARCHAR))) AS QTD_UCS,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS LINHAS_DIC_FIC,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '1' THEN 1 ELSE 0 END) AS LINHAS_DICRI,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) IN ('5', '6') THEN 1 ELSE 0 END) AS LINHAS_DISE,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS FIC,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS DIC,
                MAX(COALESCE(DURACAO_HORA, 0)) AS MAX_DURACAO_H,
                SUM(CASE WHEN COALESCE(DURACAO_HORA, 0) >= 24 THEN 1 ELSE 0 END) AS QTD_DURACAO_GE_24H,
                SUM(CASE WHEN COALESCE(DURACAO_HORA, 0) < 0 THEN 1 ELSE 0 END) AS QTD_DURACAO_NEGATIVA,
                SUM(CASE WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL THEN 1 ELSE 0 END) AS QTD_MANOBRA,
                COUNT(DISTINCT TRIM(CAST(COD_TIPO_INTRP AS VARCHAR))) AS QTD_COD_TIPO_INTRP,
                COUNT(DISTINCT TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR))) AS QTD_TIPO_PROTOC_UCI,
                {valid_pos_expression} AS VALID_POS_OPERACAO
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY COALESCE(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), 'SEM_OCORRENCIA')
        ),
        sem_uc AS (
            SELECT
                COALESCE(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), 'SEM_OCORRENCIA') AS NUM_OCORRENCIA_ADMS,
                MAX(CASE WHEN OCORRENCIA_SEM_UC_APURAVEL = 'SIM' THEN 1 ELSE 0 END) AS OCORRENCIA_SEM_UC_COMPLETA,
                SUM(QTD_INTERRUPCOES_SEM_UC_APURAVEL) AS QTD_INTERRUPCOES_SEM_UC_APURAVEL,
                MAX(ACAO_SUGERIDA_AUDITORIA) AS ACAO_SUGERIDA_AUDITORIA
            FROM gold_ocorrencia_sem_uc
            GROUP BY COALESCE(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), 'SEM_OCORRENCIA')
        ),
        ocorrencia_uc AS (
            SELECT DISTINCT
                COALESCE(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), 'SEM_OCORRENCIA') AS NUM_OCORRENCIA_ADMS,
                CAST(NUM_UC_UCI AS VARCHAR) AS UC
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
        ),
        ressarcimento AS (
            SELECT
                ou.NUM_OCORRENCIA_ADMS,
                COUNT(DISTINCT r.UC) AS UCS_COM_COMPENSACAO,
                SUM(COALESCE(r.COMP_TOTAL_PRODIST, 0)) AS COMP_TOTAL_PRODIST
            FROM ocorrencia_uc ou
            JOIN gold_ressarcimento_prodist r
              ON r.UC = ou.UC
            WHERE COALESCE(r.COMP_TOTAL_PRODIST, 0) > 0
            GROUP BY ou.NUM_OCORRENCIA_ADMS
        ),
        score_bruto AS (
            SELECT
                a.*,
                COALESCE(s.OCORRENCIA_SEM_UC_COMPLETA, 0) AS OCORRENCIA_SEM_UC_COMPLETA,
                COALESCE(s.QTD_INTERRUPCOES_SEM_UC_APURAVEL, 0) AS QTD_INTERRUPCOES_SEM_UC_APURAVEL,
                COALESCE(s.ACAO_SUGERIDA_AUDITORIA, 'OK') AS ACAO_SUGERIDA_AUDITORIA,
                COALESCE(r.UCS_COM_COMPENSACAO, 0) AS UCS_COM_COMPENSACAO,
                COALESCE(r.COMP_TOTAL_PRODIST, 0) AS COMP_TOTAL_PRODIST,
                (
                    CASE WHEN COALESCE(s.OCORRENCIA_SEM_UC_COMPLETA, 0) = 1 THEN 100 ELSE 0 END
                  + CASE WHEN COALESCE(s.QTD_INTERRUPCOES_SEM_UC_APURAVEL, 0) > 0 THEN 50 ELSE 0 END
                  + CASE WHEN a.QTD_DURACAO_GE_24H > 0 THEN 40 ELSE 0 END
                  + CASE WHEN a.MAX_DURACAO_H >= 24 THEN 30 ELSE 0 END
                  + CASE WHEN a.QTD_COD_TIPO_INTRP > 1 THEN 20 ELSE 0 END
                  + CASE WHEN a.QTD_TIPO_PROTOC_UCI > 1 THEN 15 ELSE 0 END
                  + CASE WHEN COALESCE(r.COMP_TOTAL_PRODIST, 0) > 0 THEN 20 ELSE 0 END
                  + LEAST(30, CAST(a.QTD_UCS / 1000 AS INTEGER))
                  + LEAST(30, CAST(a.DIC / 100 AS INTEGER))
                ) AS SCORE_BRUTO,
                CONCAT_WS(
                    '; ',
                    CASE WHEN COALESCE(s.OCORRENCIA_SEM_UC_COMPLETA, 0) = 1 THEN 'ocorrencia completa sem UC apuravel' END,
                    CASE WHEN COALESCE(s.QTD_INTERRUPCOES_SEM_UC_APURAVEL, 0) > 0 THEN 'interrupcao sem UC apuravel' END,
                    CASE WHEN a.QTD_DURACAO_GE_24H > 0 THEN 'duracao >= 24h' END,
                    CASE WHEN a.QTD_COD_TIPO_INTRP > 1 THEN 'mais de um COD_TIPO_INTRP' END,
                    CASE WHEN a.QTD_TIPO_PROTOC_UCI > 1 THEN 'mais de um TIPO_PROTOC_JUSTIF_UCI' END,
                    CASE WHEN COALESCE(r.COMP_TOTAL_PRODIST, 0) > 0 THEN 'impacto financeiro estimado' END
                ) AS MOTIVOS_PRIORIDADE
            FROM ocorrencia_apuracao a
            LEFT JOIN sem_uc s
              ON s.NUM_OCORRENCIA_ADMS = a.NUM_OCORRENCIA_ADMS
            LEFT JOIN ressarcimento r
              ON r.NUM_OCORRENCIA_ADMS = a.NUM_OCORRENCIA_ADMS
        ),
        score AS (
            SELECT
                *,
                LEAST(100, SCORE_BRUTO) AS SCORE_PRIORIDADE,
                CASE
                    WHEN LEAST(100, SCORE_BRUTO) <= 29 THEN 'Baixo'
                    WHEN LEAST(100, SCORE_BRUTO) <= 59 THEN 'Médio'
                    WHEN LEAST(100, SCORE_BRUTO) <= 79 THEN 'Alto'
                    ELSE 'Crítico'
                END AS FAIXA_SCORE,
                CASE
                    WHEN VALID_POS_OPERACAO = 'S' AND LEAST(100, SCORE_BRUTO) >= 60
                        THEN 'Validado pós-operação'
                    WHEN VALID_POS_OPERACAO = 'S'
                        THEN 'Validado'
                    WHEN LEAST(100, SCORE_BRUTO) >= 60
                        THEN 'Pendente prioritário'
                    ELSE 'Pendente comum'
                END AS STATUS_ANALITICO
            FROM score_bruto
        )
        SELECT *
        FROM score
        WHERE SCORE_PRIORIDADE >= {int(min_score)}
        ORDER BY
            CASE WHEN VALID_POS_OPERACAO = 'S' THEN 1 ELSE 0 END,
            SCORE_PRIORIDADE DESC,
            COMP_TOTAL_PRODIST DESC,
            DIC DESC,
            QTD_UCS DESC
        LIMIT {int(limit)}
    """
    return query_df(db_path, sql)


@st.cache_data(show_spinner=False)
def analytics_occurrence_detail(db_path: str, occurrence_id: str, limit: int) -> pd.DataFrame:
    safe_occurrence = sql_literal_for_streamlit(occurrence_id)
    valid_pos_column = (
        "VALID_POS_OPERACAO,"
        if column_exists(db_path, "gold_apuracao_uc", "VALID_POS_OPERACAO")
        else "'N' AS VALID_POS_OPERACAO,"
    )
    sql = f"""
        SELECT
            REGIONAL,
            NUM_OCORRENCIA_ADMS,
            NUM_SEQ_INTRP,
            NUM_INTRP_UCI,
            NUM_POSTO_UCI,
            NUM_UC_UCI,
            COD_TIPO_INTRP,
            TIPO_PROTOC_JUSTIF_UCI,
            COD_CAUSA_INTRP,
            COD_COMP_INTRP,
            {valid_pos_column}
            DATA_HORA_INIC_INTRP,
            DTHR_INICIO_INTRP_UC,
            DATA_HORA_FIM_INTRP,
            DURACAO_HORA,
            CI_LIQUIDO,
            CHI_LIQUIDO
        FROM gold_apuracao_uc
        WHERE TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) = {safe_occurrence}
        ORDER BY DATA_HORA_INIC_INTRP, DTHR_INICIO_INTRP_UC, NUM_SEQ_INTRP, NUM_UC_UCI
        LIMIT {int(limit)}
    """
    return query_df(db_path, sql)


def sql_literal_for_streamlit(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


@st.cache_data(show_spinner=False)
def read_csv_preview(path: str, rows: int) -> pd.DataFrame:
    first_line = ""
    with Path(path).open("r", encoding="utf-8", errors="replace") as file:
        for line in file:
            if line.strip():
                first_line = line
                break

    separators = ["|", ";", "\t", ","]
    separator = max(separators, key=first_line.count) if first_line else "|"
    if first_line.count(separator) == 0:
        separator = "|"

    return pd.read_csv(path, sep=separator, engine="python", nrows=rows)


@st.cache_data(show_spinner=False)
def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def require_table(db_path: str, table_name: str) -> bool:
    if table_exists(db_path, table_name):
        return True

    st.warning(f"Tabela `{table_name}` não encontrada no DuckDB processado.")
    return False


def show_metric_cards(metrics: list[tuple[str, object, str | None]]) -> None:
    columns = st.columns(len(metrics))
    for column, (label, value, help_text) in zip(columns, metrics):
        column.metric(label, format_number(value), help=help_text)

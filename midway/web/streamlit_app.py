from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from midway import __version__


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
MARTS_DIR = DATA_DIR / "marts"
PROCESSED_DIR = DATA_DIR / "processed"
DEFAULT_ANOMES = os.getenv("ANOMES", "202606")


st.set_page_config(
    page_title="MIDWAY - Qualidade ADMS/IQS",
    page_icon="⚡",
    layout="wide",
)


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
    causa71_select_sql = "CAUSA71," if tem_causa71 else "'N' AS CAUSA71,"
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
            DIC_BASE_COMPENSACAO,
            FIC_BASE_COMPENSACAO,
            DMIC_BASE_COMPENSACAO,
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


def show_analytics(db_path: str, sample_limit: int) -> None:
    st.subheader("Analytics Pós-Operação")
    st.caption(
        "Ranking estatístico para priorizar ocorrências que merecem verificação manual "
        "antes de aceitar a apuração e o ressarcimento."
    )

    required_tables = [
        "gold_apuracao_uc",
        "gold_ocorrencia_sem_uc",
        "gold_ressarcimento_prodist",
    ]
    if not all(require_table(db_path, table_name) for table_name in required_tables):
        return

    overview = analytics_overview(db_path).iloc[0]
    show_metric_cards(
        [
            ("Ocorrências", overview["OCORRENCIAS_APURAVEIS"], "Com UCs apuráveis"),
            ("Duração >= 24h", overview["LINHAS_DURACAO_GE_24H"], "Linhas UC com duração longa"),
            ("Ocorr. sem UC", overview["OCORRENCIAS_COM_INTERRUPCAO_SEM_UC"], "Com interrupção sem UC apurável"),
            ("Comp. estimada", overview["COMP_TOTAL_PRODIST"], "Soma PRODIST prévia"),
        ]
    )

    st.info(
        "`VALID_POS_OPERACAO = S` indica ocorrência já verificada e aceita pela pós-operação. "
        "Ela continua visível no ranking, mas deixa de ser tratada como pendência comum."
    )

    left, middle, right = st.columns([1, 1, 1])
    with left:
        min_score = st.slider(
            "Score mínimo",
            0,
            100,
            40,
            step=5,
            help="Score maior combina risco operacional, sem UC, duração alta e impacto financeiro.",
        )
    with middle:
        score_filter = st.selectbox(
            "Faixa de score",
            ["Todos", "Baixo", "Médio", "Alto", "Crítico"],
        )
    with right:
        validacao_filter = st.selectbox(
            "Validação Pós-Operação",
            ["Todos", "Somente validados", "Somente não validados"],
        )

    pendencia_filter = st.radio(
        "Pendência",
        ["Todos", "Pendentes", "Validados"],
        horizontal=True,
        help="Combina o score analytics com a validação operacional.",
    )

    ranking_df = analytics_occurrences(db_path, min_score, sample_limit * 5)
    if ranking_df.empty:
        st.success("Nenhuma ocorrência encontrada para o score informado.")
        return

    ranking_df["VALID_POS_OPERACAO"] = ranking_df["VALID_POS_OPERACAO"].fillna("N").astype(str).str.upper()

    if score_filter != "Todos":
        ranking_df = ranking_df[ranking_df["FAIXA_SCORE"] == score_filter]

    if validacao_filter == "Somente validados":
        ranking_df = ranking_df[ranking_df["VALID_POS_OPERACAO"] == "S"]
    elif validacao_filter == "Somente não validados":
        ranking_df = ranking_df[ranking_df["VALID_POS_OPERACAO"] != "S"]

    if pendencia_filter == "Pendentes":
        ranking_df = ranking_df[ranking_df["VALID_POS_OPERACAO"] != "S"]
    elif pendencia_filter == "Validados":
        ranking_df = ranking_df[ranking_df["VALID_POS_OPERACAO"] == "S"]

    ranking_df = ranking_df.head(sample_limit)
    if ranking_df.empty:
        st.success("Nenhuma ocorrência encontrada para os filtros informados.")
        return

    qtd_validadas = int((ranking_df["VALID_POS_OPERACAO"] == "S").sum())
    qtd_pendentes = int((ranking_df["VALID_POS_OPERACAO"] != "S").sum())
    qtd_criticas = int((ranking_df["FAIXA_SCORE"] == "Crítico").sum())
    qtd_criticas_pendentes = int(
        ((ranking_df["FAIXA_SCORE"] == "Crítico") & (ranking_df["VALID_POS_OPERACAO"] != "S")).sum()
    )

    show_metric_cards(
        [
            ("Ocorrências exibidas", len(ranking_df), "Após filtros do painel"),
            ("Validadas pós", qtd_validadas, "VALID_POS_OPERACAO = S"),
            ("Pendentes", qtd_pendentes, "VALID_POS_OPERACAO diferente de S"),
            ("Críticas pendentes", qtd_criticas_pendentes, "Score crítico ainda não validado"),
        ]
    )

    score_summary = (
        ranking_df.groupby(["FAIXA_SCORE", "VALID_POS_OPERACAO"], dropna=False)
        .size()
        .reset_index(name="QTD_OCORRENCIAS")
        .sort_values(["FAIXA_SCORE", "VALID_POS_OPERACAO"])
    )
    with st.expander("Resumo por faixa de score e validação", expanded=False):
        st.dataframe(score_summary, use_container_width=True, hide_index=True)
        st.caption(f"Ocorrências críticas no recorte: {qtd_criticas}.")

    st.markdown("#### Ocorrências prioritárias")
    st.dataframe(
        ranking_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SCORE_PRIORIDADE": st.column_config.ProgressColumn(
                "SCORE",
                min_value=0,
                max_value=100,
            ),
            "FAIXA_SCORE": st.column_config.TextColumn("Faixa"),
            "VALID_POS_OPERACAO": st.column_config.TextColumn("Validado Pós"),
            "STATUS_ANALITICO": st.column_config.TextColumn("Status"),
            "COMP_TOTAL_PRODIST": st.column_config.NumberColumn("COMP_TOTAL_PRODIST", format="%.2f"),
            "DIC": st.column_config.NumberColumn("DIC", format="%.3f"),
            "MAX_DURACAO_H": st.column_config.NumberColumn("MAX_DURACAO_H", format="%.3f"),
        },
    )
    st.download_button(
        "Baixar ranking exibido",
        ranking_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="analytics_ocorrencias_prioritarias.csv",
        mime="text/csv",
    )

    selected_occurrence = st.selectbox(
        "Ocorrência para detalhar",
        ranking_df["NUM_OCORRENCIA_ADMS"].astype(str).tolist(),
    )
    selected_row = ranking_df[
        ranking_df["NUM_OCORRENCIA_ADMS"].astype(str) == str(selected_occurrence)
    ].iloc[0]
    st.markdown("#### Resumo da ocorrência selecionada")
    st.dataframe(pd.DataFrame([selected_row]), use_container_width=True, hide_index=True)

    st.markdown("#### Linhas UC/interrupção da ocorrência")
    detail_df = analytics_occurrence_detail(db_path, str(selected_occurrence), sample_limit)
    st.dataframe(detail_df, use_container_width=True, hide_index=True)
    st.download_button(
        "Baixar detalhe da ocorrência",
        detail_df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"analytics_ocorrencia_{selected_occurrence}.csv",
        mime="text/csv",
    )


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


st.title("⚡ MIDWAY - Painel de Qualidade ADMS/IQS")
st.caption(f"Versão {__version__}")

with st.sidebar:
    st.header("Configuração")
    st.caption(f"MIDWAY {__version__}")
    page = st.radio(
        "Página",
        ["Conferência ETL", "Analytics Pós-Operação"],
        help="Separe conferência do fluxo ETL das análises estatísticas para pós-operação.",
    )
    anomes = st.text_input("ANOMES", value=DEFAULT_ANOMES)
    db_path = processed_path(anomes)
    st.caption(f"DuckDB: `{db_path}`")
    sample_limit = st.slider("Linhas de amostra", 50, 5000, 500, step=50)
    preview_rows = st.slider("Linhas de prévia CSV", 20, 1000, 100, step=20)
    refresh = st.button("Limpar cache")

if refresh:
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

if not db_path.exists():
    st.error(f"DuckDB processado não encontrado: `{db_path}`")
    st.stop()

if page == "Analytics Pós-Operação":
    show_analytics(str(db_path), sample_limit)
else:
    tabs = st.tabs(
        [
            "Qualidade",
            "Sobreposição",
            "DIC/FIC",
            "Ressarcimento",
            "Arquivos",
            "SQL",
        ]
    )

    with tabs[0]:
        show_quality_metrics(anomes)

    with tabs[1]:
        show_overlaps(str(db_path), sample_limit)

    with tabs[2]:
        show_dic_fic(str(db_path))

    with tabs[3]:
        show_prodist(str(db_path), sample_limit)

    with tabs[4]:
        show_marts(anomes, preview_rows)

    with tabs[5]:
        show_sql(str(db_path), sample_limit)

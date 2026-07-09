from pathlib import Path


ROOT = Path(".")
ANALYTICS_DIR = ROOT / "midway" / "analytics"
OUTLIER_PATH = ANALYTICS_DIR / "outlier_uc.py"
INIT_PATH = ANALYTICS_DIR / "__init__.py"
AVALIACAO_PATH = ROOT / "midway" / "web" / "library" / "avaliacao_uc.py"
RUN_BAT = ROOT / "run.bat"


OUTLIER_CODE = r'''from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DIR = BASE_DIR / "processed"
MARTS_DIR = BASE_DIR / "marts"

PROCESSED_DUCKDB_PATH = PROCESSED_DIR / f"iqs_adms_processed_{ANOMES}.duckdb"
TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")


def tabela_existe(con, nome_tabela: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [nome_tabela],
        ).fetchone()[0]
        > 0
    )


def colunas(con, tabela: str) -> list[str]:
    if not tabela_existe(con, tabela):
        return []

    return [
        row[0]
        for row in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = ?
            ORDER BY ordinal_position
            """,
            [tabela],
        ).fetchall()
    ]


def primeira_coluna_existente(colunas_tabela: list[str], candidatas: list[str]) -> str | None:
    mapa = {col.upper(): col for col in colunas_tabela}
    for candidata in candidatas:
        if candidata.upper() in mapa:
            return mapa[candidata.upper()]
    return None


def origem_tensao(con) -> tuple[str | None, str | None, str | None, str | None]:
    tabelas = [
        "gold_ressarcimento_prodist",
        "gold_continuidade_uc",
        "gold_consumidores",
        "silver_iqs_vrc",
        "gold_vrc",
    ]

    for tabela in tabelas:
        cols = colunas(con, tabela)
        if not cols:
            continue

        col_uc = primeira_coluna_existente(
            cols,
            ["UC", "NUM_UC", "NUM_UC_UCI", "ISN_UC", "NUM_UC_HCAI"],
        )
        col_grupo = primeira_coluna_existente(
            cols,
            [
                "COD_GRUPO_NIVEL_TENSAO_UC",
                "COD_GRUPO_NIVEL_TENSAO",
                "GRUPO_NIVEL_TENSAO_UC",
                "GRUPO_NIVEL_TENSAO",
                "GRUPO_TENSAO",
                "COD_GRUPO_TENSAO",
            ],
        )
        col_nivel = primeira_coluna_existente(
            cols,
            [
                "COD_NIVEL_TENSAO_UC",
                "COD_NIVEL_TENSAO",
                "NIVEL_TENSAO_UC",
                "NIVEL_TENSAO",
            ],
        )

        if col_uc and (col_grupo or col_nivel):
            return tabela, col_uc, col_grupo, col_nivel

    return None, None, None, None


def criar_gold_outlier_uc(con):
    obrigatorias = ["gold_apuracao_uc", "gold_ressarcimento_prodist"]
    ausentes = [tabela for tabela in obrigatorias if not tabela_existe(con, tabela)]
    if ausentes:
        raise RuntimeError(f"Tabelas ausentes para gold_outlier_uc: {ausentes}")

    apuracao_cols = colunas(con, "gold_apuracao_uc")
    tem_valid_pos = "VALID_POS_OPERACAO" in {col.upper() for col in apuracao_cols}
    valid_pos_expr = (
        "UPPER(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR)))"
        if tem_valid_pos
        else "'N'"
    )

    tabela_tensao, col_uc_tensao, col_grupo, col_nivel = origem_tensao(con)

    if tabela_tensao and col_uc_tensao:
        grupo_expr = (
            f'MAX(NULLIF(TRIM(CAST("{col_grupo}" AS VARCHAR)), \'\'))'
            if col_grupo
            else "NULL"
        )
        nivel_expr = (
            f'MAX(NULLIF(TRIM(CAST("{col_nivel}" AS VARCHAR)), \'\'))'
            if col_nivel
            else "NULL"
        )
        tensao_cte = f"""
        tensao_uc AS (
            SELECT
                TRIM(CAST("{col_uc_tensao}" AS VARCHAR)) AS UC,
                {grupo_expr} AS COD_GRUPO_NIVEL_TENSAO_UC,
                {nivel_expr} AS COD_NIVEL_TENSAO_UC
            FROM {tabela_tensao}
            WHERE NULLIF(TRIM(CAST("{col_uc_tensao}" AS VARCHAR)), '') IS NOT NULL
            GROUP BY TRIM(CAST("{col_uc_tensao}" AS VARCHAR))
        ),
        """
        tensao_join = "LEFT JOIN tensao_uc t ON t.UC = e.UC"
        grupo_select = "t.COD_GRUPO_NIVEL_TENSAO_UC"
        nivel_select = "t.COD_NIVEL_TENSAO_UC"
    else:
        tensao_cte = """
        tensao_uc AS (
            SELECT
                NULL AS UC,
                NULL AS COD_GRUPO_NIVEL_TENSAO_UC,
                NULL AS COD_NIVEL_TENSAO_UC
            WHERE FALSE
        ),
        """
        tensao_join = "LEFT JOIN tensao_uc t ON t.UC = e.UC"
        grupo_select = "NULL"
        nivel_select = "NULL"

    con.execute(
        f"""
        CREATE OR REPLACE TABLE gold_outlier_uc AS
        WITH eventos_uc AS (
            SELECT
                TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS UC,
                ANY_VALUE(REGIONAL) AS REGIONAL,
                ANY_VALUE(COD_CONJTO_ELET_ANEEL_INTRP) AS CONJUNTO,

                COUNT(*) AS QTD_INTERRUPCOES,
                COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS,
                COUNT(DISTINCT CASE WHEN {valid_pos_expr} = 'S' THEN NUM_OCORRENCIA_ADMS END) AS QTD_OCORRENCIAS_VALIDADAS_POS,
                COUNT(DISTINCT CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN NUM_OCORRENCIA_ADMS END) AS QTD_OCORRENCIAS_PENDENTES_POS,

                SUM(COALESCE(CI_LIQUIDO, 0)) AS FIC,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS DIC,
                MAX(COALESCE(CHI_LIQUIDO, 0)) AS DMIC,

                SUM(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN COALESCE(CI_LIQUIDO, 0) ELSE 0 END) AS FIC_PENDENTE_POS,
                SUM(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS DIC_PENDENTE_POS,
                MAX(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS DMIC_PENDENTE_POS,

                SUM(CASE WHEN COALESCE(DURACAO_HORA, 0) >= 24 THEN 1 ELSE 0 END) AS QTD_DURACAO_GE_24H,
                SUM(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' AND COALESCE(DURACAO_HORA, 0) >= 24 THEN 1 ELSE 0 END) AS QTD_DURACAO_GE_24H_PENDENTE_POS,

                SUM(CASE WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL THEN 1 ELSE 0 END) AS QTD_MANOBRA,

                COUNT(DISTINCT TIPO_PROTOC_JUSTIF_UCI) AS QTD_TIPOS_PROTOCOLO,
                COUNT(DISTINCT CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' THEN TIPO_PROTOC_JUSTIF_UCI END) AS QTD_TIPOS_PROTOCOLO_PENDENTE_POS,

                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS CHI_TIPO_0,
                SUM(CASE WHEN COALESCE({valid_pos_expr}, 'N') <> 'S' AND TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS CHI_TIPO_0_PENDENTE_POS,
                SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) <> '0' THEN COALESCE(CHI_LIQUIDO, 0) ELSE 0 END) AS CHI_TIPO_NAO_0
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
            GROUP BY TRIM(CAST(NUM_UC_UCI AS VARCHAR))
        ),
        continuidade AS (
            SELECT
                TRIM(CAST(UC AS VARCHAR)) AS UC,
                COALESCE(META_DIC, 0) AS META_DIC,
                COALESCE(META_FIC, 0) AS META_FIC,
                COALESCE(META_DMIC, 0) AS META_DMIC,
                COALESCE(COMP_TOTAL_PRODIST, 0) AS COMP_TOTAL_PRODIST
            FROM gold_ressarcimento_prodist
        ),
        {tensao_cte}
        score AS (
            SELECT
                e.*,
                {grupo_select} AS COD_GRUPO_NIVEL_TENSAO_UC,
                {nivel_select} AS COD_NIVEL_TENSAO_UC,

                c.META_DIC,
                c.META_FIC,
                c.META_DMIC,
                c.COMP_TOTAL_PRODIST,

                CASE
                    WHEN e.QTD_OCORRENCIAS_PENDENTES_POS > 0 THEN COALESCE(c.COMP_TOTAL_PRODIST, 0)
                    ELSE 0
                END AS COMP_TOTAL_PRODIST_PENDENTE_POS,

                CASE
                    WHEN e.QTD_OCORRENCIAS = e.QTD_OCORRENCIAS_VALIDADAS_POS AND e.QTD_OCORRENCIAS > 0 THEN 'Validado pós'
                    WHEN e.QTD_OCORRENCIAS_VALIDADAS_POS > 0 THEN 'Parcialmente validado'
                    ELSE 'Pendente pós'
                END AS STATUS_POS_OPERACAO,

                CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC / c.META_DIC * 100 ELSE 0 END AS PCT_META_DIC,
                CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC / c.META_FIC * 100 ELSE 0 END AS PCT_META_FIC,
                CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC / c.META_DMIC * 100 ELSE 0 END AS PCT_META_DMIC,

                CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC_PENDENTE_POS / c.META_DIC * 100 ELSE 0 END AS PCT_META_DIC_PENDENTE_POS,
                CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC_PENDENTE_POS / c.META_FIC * 100 ELSE 0 END AS PCT_META_FIC_PENDENTE_POS,
                CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC_PENDENTE_POS / c.META_DMIC * 100 ELSE 0 END AS PCT_META_DMIC_PENDENTE_POS,

                (
                    LEAST(CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC / c.META_DIC * 30 ELSE 0 END, 30)
                  + LEAST(CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC / c.META_FIC * 20 ELSE 0 END, 20)
                  + LEAST(CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC / c.META_DMIC * 20 ELSE 0 END, 20)
                  + LEAST(e.QTD_DURACAO_GE_24H * 10, 10)
                  + LEAST(e.QTD_TIPOS_PROTOCOLO * 5, 10)
                  + LEAST(COALESCE(c.COMP_TOTAL_PRODIST, 0) / 10000.0, 10)
                ) AS SCORE_OUTLIER_UC,

                (
                    LEAST(CASE WHEN COALESCE(c.META_DIC, 0) > 0 THEN e.DIC_PENDENTE_POS / c.META_DIC * 30 ELSE 0 END, 30)
                  + LEAST(CASE WHEN COALESCE(c.META_FIC, 0) > 0 THEN e.FIC_PENDENTE_POS / c.META_FIC * 20 ELSE 0 END, 20)
                  + LEAST(CASE WHEN COALESCE(c.META_DMIC, 0) > 0 THEN e.DMIC_PENDENTE_POS / c.META_DMIC * 20 ELSE 0 END, 20)
                  + LEAST(e.QTD_DURACAO_GE_24H_PENDENTE_POS * 10, 10)
                  + LEAST(e.QTD_TIPOS_PROTOCOLO_PENDENTE_POS * 5, 10)
                  + LEAST(
                        CASE WHEN e.QTD_OCORRENCIAS_PENDENTES_POS > 0 THEN COALESCE(c.COMP_TOTAL_PRODIST, 0) ELSE 0 END / 10000.0,
                        10
                    )
                ) AS SCORE_OUTLIER_UC_PENDENTE
            FROM eventos_uc e
            LEFT JOIN continuidade c
              ON c.UC = e.UC
            {tensao_join}
        )
        SELECT
            *,
            CASE
                WHEN SCORE_OUTLIER_UC >= 80 THEN 'Crítico'
                WHEN SCORE_OUTLIER_UC >= 60 THEN 'Alto'
                WHEN SCORE_OUTLIER_UC >= 40 THEN 'Médio'
                ELSE 'Baixo'
            END AS FAIXA_OUTLIER,
            CASE
                WHEN SCORE_OUTLIER_UC_PENDENTE >= 80 THEN 'Crítico'
                WHEN SCORE_OUTLIER_UC_PENDENTE >= 60 THEN 'Alto'
                WHEN SCORE_OUTLIER_UC_PENDENTE >= 40 THEN 'Médio'
                ELSE 'Baixo'
            END AS FAIXA_OUTLIER_PENDENTE
        FROM score
        """
    )

    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_outlier_uc_uc ON gold_outlier_uc(UC)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_outlier_uc_regional ON gold_outlier_uc(REGIONAL)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_outlier_uc_conjunto ON gold_outlier_uc(CONJUNTO)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_outlier_uc_grupo_tensao ON gold_outlier_uc(COD_GRUPO_NIVEL_TENSAO_UC)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_outlier_uc_nivel_tensao ON gold_outlier_uc(COD_NIVEL_TENSAO_UC)")


def exportar_resumo(con):
    MARTS_DIR.mkdir(parents=True, exist_ok=True)

    csv_path = MARTS_DIR / f"Gold_Outlier_UC_{ANOMES}_{TIMESTAMP}.CSV"
    resumo_path = MARTS_DIR / f"Gold_Outlier_UC_{ANOMES}_{TIMESTAMP}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_outlier_uc
            ORDER BY
                SCORE_OUTLIER_UC_PENDENTE DESC,
                COMP_TOTAL_PRODIST_PENDENTE_POS DESC,
                DIC_PENDENTE_POS DESC
            LIMIT 10000
        )
        TO '{csv_path.as_posix()}'
        WITH (HEADER TRUE, DELIMITER '|')
        """
    )

    row = con.execute(
        """
        SELECT
            COUNT(*) AS UCS,
            SUM(QTD_OCORRENCIAS_PENDENTES_POS) AS OCORRENCIAS_PENDENTES_POS,
            SUM(QTD_OCORRENCIAS_VALIDADAS_POS) AS OCORRENCIAS_VALIDADAS_POS,
            SUM(COMP_TOTAL_PRODIST_PENDENTE_POS) AS COMP_PENDENTE,
            SUM(COMP_TOTAL_PRODIST) AS COMP_TOTAL,
            MAX(SCORE_OUTLIER_UC_PENDENTE) AS MAIOR_SCORE_PENDENTE
        FROM gold_outlier_uc
        """
    ).fetchone()

    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("GOLD OUTLIER UC\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write("Tabela: gold_outlier_uc\n")
        arquivo.write(f"UCs: {row[0]}\n")
        arquivo.write(f"Ocorrencias pendentes pos: {row[1]}\n")
        arquivo.write(f"Ocorrencias validadas pos: {row[2]}\n")
        arquivo.write(f"Compensacao pendente: {row[3]}\n")
        arquivo.write(f"Compensacao total: {row[4]}\n")
        arquivo.write(f"Maior score pendente: {row[5]}\n")
        arquivo.write(f"CSV: {csv_path}\n")

    print("gold_outlier_uc criada.")
    print(f"CSV: {csv_path}")
    print(f"Resumo: {resumo_path}")


def materializar_gold_outlier_uc():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    try:
        criar_gold_outlier_uc(con)
        exportar_resumo(con)
    finally:
        con.close()


if __name__ == "__main__":
    materializar_gold_outlier_uc()
'''


OUTLIER_RANKING_FUNC = r'''@st.cache_data(show_spinner=False)
def outlier_uc_ranking(
    db_path: str,
    sample_limit: int,
    grupos_tensao: tuple[str, ...] = (),
    niveis_tensao: tuple[str, ...] = (),
):
    filtros = ""

    if grupos_tensao:
        valores = ", ".join(sql_literal_for_streamlit(str(value)) for value in grupos_tensao)
        filtros += f"""
          AND NULLIF(TRIM(CAST(COD_GRUPO_NIVEL_TENSAO_UC AS VARCHAR)), '') IN ({valores})
        """

    if niveis_tensao:
        valores = ", ".join(sql_literal_for_streamlit(str(value)) for value in niveis_tensao)
        filtros += f"""
          AND NULLIF(TRIM(CAST(COD_NIVEL_TENSAO_UC AS VARCHAR)), '') IN ({valores})
        """

    return query_df(
        db_path,
        f"""
        SELECT *
        FROM gold_outlier_uc
        WHERE 1 = 1
          {filtros}
        ORDER BY
            SCORE_OUTLIER_UC_PENDENTE DESC,
            COMP_TOTAL_PRODIST_PENDENTE_POS DESC,
            DIC_PENDENTE_POS DESC,
            FIC_PENDENTE_POS DESC
        LIMIT {int(sample_limit)}
        """,
    )
'''


FILTER_OPTIONS_FUNC = r'''@st.cache_data(show_spinner=False)
def filter_options_consumidores(db_path: str, tipo: str):
    if require_table(db_path, "gold_outlier_uc"):
        column_name = (
            "COD_GRUPO_NIVEL_TENSAO_UC"
            if tipo == "grupo"
            else "COD_NIVEL_TENSAO_UC"
        )

        df = query_df(
            db_path,
            f"""
            SELECT DISTINCT
                NULLIF(TRIM(CAST({column_name} AS VARCHAR)), '') AS VALOR
            FROM gold_outlier_uc
            WHERE NULLIF(TRIM(CAST({column_name} AS VARCHAR)), '') IS NOT NULL
            ORDER BY VALOR
            """,
        )

        if not df.empty:
            return df["VALOR"].astype(str).tolist()

    table_name, actual_column = _coluna_tensao_uc(db_path, tipo)
    if not table_name or not actual_column:
        return []

    df = query_df(
        db_path,
        f"""
        SELECT DISTINCT
            NULLIF(TRIM(CAST("{actual_column}" AS VARCHAR)), '') AS VALOR
        FROM {table_name}
        WHERE NULLIF(TRIM(CAST("{actual_column}" AS VARCHAR)), '') IS NOT NULL
        ORDER BY VALOR
        """,
    )

    if df.empty:
        return []

    return df["VALOR"].astype(str).tolist()
'''


def replace_between(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        raise RuntimeError(f"Marcador inicial nao encontrado: {start_marker}")

    end = text.find(end_marker, start)
    if end == -1:
        raise RuntimeError(f"Marcador final nao encontrado: {end_marker}")

    return text[:start] + replacement.rstrip() + "\n\n" + text[end:]


def implantar_outlier_module():
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
    INIT_PATH.write_text("", encoding="utf-8")
    OUTLIER_PATH.write_text(OUTLIER_CODE, encoding="utf-8")
    print(f"Criado: {OUTLIER_PATH}")


def atualizar_avaliacao_uc():
    if not AVALIACAO_PATH.exists():
        raise RuntimeError(f"Arquivo nao encontrado: {AVALIACAO_PATH}")

    text = AVALIACAO_PATH.read_text(encoding="utf-8")

    if "def filter_options_consumidores" in text:
        text = replace_between(
            text,
            "@st.cache_data(show_spinner=False)\ndef filter_options_consumidores(",
            "\ndef _sql_filter_consumidor(",
            FILTER_OPTIONS_FUNC,
        )

    text = replace_between(
        text,
        "@st.cache_data(show_spinner=False)\ndef outlier_uc_ranking(",
        "\ndef show_outlier_uc(",
        OUTLIER_RANKING_FUNC,
    )

    text = text.replace(
        'required_tables = ["gold_apuracao_uc", "gold_ressarcimento_prodist"]',
        'required_tables = ["gold_outlier_uc"]',
    )

    text = text.replace(
        'st.success("Nenhum outlier UC encontrado.")',
        'st.info("Execute `run.bat apuracao_parcial` para gerar `gold_outlier_uc`.")',
        1,
    )

    AVALIACAO_PATH.write_text(text, encoding="utf-8")
    print(f"Atualizado: {AVALIACAO_PATH}")


def atualizar_run_bat():
    if not RUN_BAT.exists():
        raise RuntimeError(f"Arquivo nao encontrado: {RUN_BAT}")

    text = RUN_BAT.read_text(encoding="utf-8", errors="ignore")
    if "midway.analytics.outlier_uc" in text:
        print("run.bat ja chama midway.analytics.outlier_uc")
        return

    lines = text.splitlines()
    novas_linhas = []
    inseriu = False

    for line in lines:
        novas_linhas.append(line)
        if "midway.apuracao.previa" in line and not inseriu:
            novas_linhas.append("if errorlevel 1 goto erro")
            novas_linhas.append("echo Gerando gold_outlier_uc...")
            novas_linhas.append('"%PYTHON%" -m midway.analytics.outlier_uc')
            novas_linhas.append("if errorlevel 1 goto erro")
            inseriu = True

    if not inseriu:
        raise RuntimeError(
            "Nao encontrei chamada para midway.apuracao.previa no run.bat. "
            "Adicione manualmente: python -m midway.analytics.outlier_uc depois da apuracao_parcial."
        )

    RUN_BAT.write_text("\n".join(novas_linhas) + "\n", encoding="utf-8")
    print(f"Atualizado: {RUN_BAT}")


def main():
    implantar_outlier_module()
    atualizar_avaliacao_uc()
    atualizar_run_bat()
    print("\nImplantacao concluida.")


if __name__ == "__main__":
    main()
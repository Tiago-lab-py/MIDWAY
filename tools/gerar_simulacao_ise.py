import csv
import os
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
MARTS_DIR = BASE_DIR / "marts"
TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")
DURACAO_MINIMA_HORA = 3.0 / 60.0

CAUSAS_ISE = (
    "2",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "13",
    "15",
    "23",
    "24",
    "28",
    "39",
    "40",
    "41",
    "52",
    "54",
    "69",
    "82",
)

REGRAS_EXPURGO_DIC_BRUTO = (
    "DFC",
    "USU",
    "USI",
    "ACI",
    "FM",
    "ERR",
    "DUP",
    "CHP",
    "DFI",
    "PTP",
)

REGRAS_EXPURGO_FIC_BRUTO = REGRAS_EXPURGO_DIC_BRUTO + ("MAN",)


def sql_lista_texto(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


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


def colunas_tabela(con, nome_tabela: str) -> set[str]:
    return {
        linha[0].upper()
        for linha in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [nome_tabela],
        ).fetchall()
    }


def coluna_texto(colunas: set[str], nome_coluna: str, padrao: str) -> str:
    if nome_coluna.upper() in colunas:
        return f"NULLIF(TRIM(CAST({nome_coluna} AS VARCHAR)), '')"
    return padrao


def coluna_numero(colunas: set[str], nome_coluna: str, padrao: str = "0") -> str:
    if nome_coluna.upper() in colunas:
        return f"COALESCE(TRY_CAST({nome_coluna} AS DOUBLE), 0)"
    return padrao


def criar_gold_simulacao_ise(con) -> None:
    if not tabela_existe(con, "gold_apuracao_uc"):
        raise RuntimeError("Tabela gold_apuracao_uc nao encontrada. Execute run.bat apuracao_parcial.")

    colunas = colunas_tabela(con, "gold_apuracao_uc")
    obrigatorias = {"NUM_UC_UCI", "COD_CAUSA_INTRP", "DURACAO_HORA"}
    faltantes = sorted(obrigatorias - colunas)
    if faltantes:
        raise RuntimeError(f"Colunas obrigatorias ausentes em gold_apuracao_uc: {', '.join(faltantes)}")

    causa = "NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), '')"
    uc = "NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')"
    duracao = coluna_numero(colunas, "DURACAO_HORA")
    num_ocorrencia = coluna_texto(colunas, "NUM_OCORRENCIA_ADMS", "NULL")
    num_interrupcao = coluna_texto(colunas, "NUM_SEQ_INTRP", "NULL")

    sigla_tiqs_dic = (
        "COALESCE(NULLIF(TRIM(CAST(SIGLA_TIQS_DIC AS VARCHAR)), ''), 'DIC_')"
        if "SIGLA_TIQS_DIC" in colunas
        else "'DIC_'"
    )
    sigla_reid_dic = coluna_texto(colunas, "SIGLA_REID_DIC", "NULL")
    sigla_tiqs_fic = (
        "COALESCE(NULLIF(TRIM(CAST(SIGLA_TIQS_FIC AS VARCHAR)), ''), 'FIC_')"
        if "SIGLA_TIQS_FIC" in colunas
        else "'FIC_'"
    )
    sigla_reid_fic = coluna_texto(colunas, "SIGLA_REID_FIC", "NULL")

    causa_ise = f"{causa} IN ({sql_lista_texto(CAUSAS_ISE)})"
    duracao_longa = f"{duracao} >= {DURACAO_MINIMA_HORA}"
    causa_ise_longa = f"{causa_ise} AND {duracao_longa}"
    dic_bruto = (
        f"SUBSTR({sigla_tiqs_dic}, 1, 4) = 'DIC_' "
        f"AND COALESCE({sigla_reid_dic}, 'X') NOT IN ({sql_lista_texto(REGRAS_EXPURGO_DIC_BRUTO)})"
    )
    dic_liquido = f"SUBSTR({sigla_tiqs_dic}, 1, 4) = 'DIC_' AND {sigla_reid_dic} IS NULL"
    fic_bruto = (
        f"SUBSTR({sigla_tiqs_fic}, 1, 4) = 'FIC_' "
        f"AND COALESCE({sigla_reid_fic}, 'X') NOT IN ({sql_lista_texto(REGRAS_EXPURGO_FIC_BRUTO)})"
    )
    fic_liquido = f"SUBSTR({sigla_tiqs_fic}, 1, 4) = 'FIC_' AND {sigla_reid_fic} IS NULL"

    con.execute(
        f"""
        CREATE OR REPLACE TABLE gold_simulacao_ise_uc AS
        WITH base AS (
            SELECT
                {uc} AS UC,
                {num_ocorrencia} AS NUM_OCORRENCIA_ADMS,
                {num_interrupcao} AS NUM_SEQ_INTRP,
                {causa} AS COD_CAUSA_INTRP,
                {duracao} AS DURACAO_HORA,
                CASE WHEN {causa_ise_longa} THEN 'S' ELSE 'N' END AS ISE_CAUSA_ELEGIVEL,
                CASE WHEN {causa_ise_longa} AND {dic_bruto} THEN {duracao} ELSE 0 END AS ISE_CHI_BRUTO_REFERENCIA,
                CASE WHEN {causa_ise_longa} AND {dic_liquido} THEN {duracao} ELSE 0 END AS ISE_CHI_LIQUIDO_RECLASSIFICAVEL,
                CASE WHEN {causa_ise_longa} AND {fic_bruto} THEN 1 ELSE 0 END AS ISE_CI_BRUTO_REFERENCIA,
                CASE WHEN {causa_ise_longa} AND {fic_liquido} THEN 1 ELSE 0 END AS ISE_CI_LIQUIDO_RECLASSIFICAVEL
            FROM gold_apuracao_uc
            WHERE {uc} IS NOT NULL
        )
        SELECT
            UC,
            CASE
                WHEN SUM(ISE_CHI_BRUTO_REFERENCIA) > 0
                  OR SUM(ISE_CI_BRUTO_REFERENCIA) > 0
                THEN 'S'
                ELSE 'N'
            END AS ISE_POTENCIAL,
            CASE
                WHEN SUM(ISE_CHI_LIQUIDO_RECLASSIFICAVEL) > 0
                  OR SUM(ISE_CI_LIQUIDO_RECLASSIFICAVEL) > 0
                THEN 'S'
                ELSE 'N'
            END AS ISE_RECLASSIFICAVEL,
            COUNT(*) AS EVENTOS_AVALIADOS,
            SUM(CASE WHEN ISE_CAUSA_ELEGIVEL = 'S' THEN 1 ELSE 0 END) AS EVENTOS_CAUSA_ISE,
            COUNT(DISTINCT CASE WHEN ISE_CAUSA_ELEGIVEL = 'S' THEN NUM_OCORRENCIA_ADMS END) AS OCORRENCIAS_CAUSA_ISE,
            SUM(ISE_CI_BRUTO_REFERENCIA) AS ISE_CI_BRUTO_REFERENCIA,
            SUM(ISE_CI_LIQUIDO_RECLASSIFICAVEL) AS ISE_CI_LIQUIDO_RECLASSIFICAVEL,
            SUM(ISE_CHI_BRUTO_REFERENCIA) AS ISE_CHI_BRUTO_REFERENCIA,
            SUM(ISE_CHI_LIQUIDO_RECLASSIFICAVEL) AS ISE_CHI_LIQUIDO_RECLASSIFICAVEL,
            MAX(ISE_CHI_BRUTO_REFERENCIA) AS ISE_DMIC_BRUTO_REFERENCIA,
            MAX(ISE_CHI_LIQUIDO_RECLASSIFICAVEL) AS ISE_DMIC_LIQUIDO_RECLASSIFICAVEL,
            STRING_AGG(DISTINCT COD_CAUSA_INTRP, ', ' ORDER BY COD_CAUSA_INTRP) FILTER (
                WHERE ISE_CAUSA_ELEGIVEL = 'S'
            ) AS COD_CAUSAS_ISE
        FROM base
        GROUP BY UC
        """
    )

    con.execute("CREATE INDEX IF NOT EXISTS idx_gold_simulacao_ise_uc ON gold_simulacao_ise_uc(UC)")


def exportar_resultados(con) -> tuple[Path, Path]:
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = MARTS_DIR / f"Gold_Simulacao_ISE_UC_{ANOMES}_{TIMESTAMP}.CSV"
    resumo_path = MARTS_DIR / f"Gold_Simulacao_ISE_UC_{ANOMES}_{TIMESTAMP}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_simulacao_ise_uc
            WHERE ISE_POTENCIAL = 'S'
               OR ISE_RECLASSIFICAVEL = 'S'
            ORDER BY
                ISE_CHI_BRUTO_REFERENCIA DESC,
                ISE_CHI_LIQUIDO_RECLASSIFICAVEL DESC,
                UC
        )
        TO '{csv_path.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )

    resumo = con.execute(
        """
        SELECT
            COUNT(*) AS UCS_AVALIADAS,
            SUM(CASE WHEN ISE_POTENCIAL = 'S' THEN 1 ELSE 0 END) AS UCS_ISE_POTENCIAL,
            SUM(CASE WHEN ISE_RECLASSIFICAVEL = 'S' THEN 1 ELSE 0 END) AS UCS_ISE_RECLASSIFICAVEL,
            SUM(EVENTOS_CAUSA_ISE) AS EVENTOS_CAUSA_ISE,
            SUM(OCORRENCIAS_CAUSA_ISE) AS OCORRENCIAS_CAUSA_ISE,
            SUM(ISE_CI_BRUTO_REFERENCIA) AS ISE_CI_BRUTO_REFERENCIA,
            SUM(ISE_CI_LIQUIDO_RECLASSIFICAVEL) AS ISE_CI_LIQUIDO_RECLASSIFICAVEL,
            SUM(ISE_CHI_BRUTO_REFERENCIA) AS ISE_CHI_BRUTO_REFERENCIA,
            SUM(ISE_CHI_LIQUIDO_RECLASSIFICAVEL) AS ISE_CHI_LIQUIDO_RECLASSIFICAVEL,
            MAX(ISE_DMIC_BRUTO_REFERENCIA) AS ISE_DMIC_BRUTO_REFERENCIA_MAX,
            MAX(ISE_DMIC_LIQUIDO_RECLASSIFICAVEL) AS ISE_DMIC_LIQUIDO_RECLASSIFICAVEL_MAX
        FROM gold_simulacao_ise_uc
        """
    ).fetchone()

    campos = [
        "UCS_AVALIADAS",
        "UCS_ISE_POTENCIAL",
        "UCS_ISE_RECLASSIFICAVEL",
        "EVENTOS_CAUSA_ISE",
        "OCORRENCIAS_CAUSA_ISE",
        "ISE_CI_BRUTO_REFERENCIA",
        "ISE_CI_LIQUIDO_RECLASSIFICAVEL",
        "ISE_CHI_BRUTO_REFERENCIA",
        "ISE_CHI_LIQUIDO_RECLASSIFICAVEL",
        "ISE_DMIC_BRUTO_REFERENCIA_MAX",
        "ISE_DMIC_LIQUIDO_RECLASSIFICAVEL_MAX",
    ]

    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("SIMULACAO ISE\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write("Tabela: gold_simulacao_ise_uc\n")
        arquivo.write(f"CSV: {csv_path}\n")
        arquivo.write("Regra: bruto verifica potencial ISE; liquido mede reclassificacao.\n")
        arquivo.write("Filtro de duração: somente eventos com DURACAO_HORA >= 3 minutos entram em CHI/CI ISE.\n")
        arquivo.write(f"Causas ISE: {', '.join(CAUSAS_ISE)}\n\n")
        for campo, valor in zip(campos, resumo):
            arquivo.write(f"{campo}: {valor}\n")

    return csv_path, resumo_path


def main() -> None:
    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    try:
        criar_gold_simulacao_ise(con)
        csv_path, resumo_path = exportar_resultados(con)
    finally:
        con.close()

    print("gold_simulacao_ise_uc criada.")
    print(f"CSV: {csv_path}")
    print(f"Resumo: {resumo_path}")


if __name__ == "__main__":
    main()

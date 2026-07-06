from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd


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

COLUNAS_REGIONAL = (
    "SIGLA_REGIONAL_INTRP_PRIM_HIADMS",
    "SIGLA_REGIONAL",
    "REGIONAL",
    "NOME_REGIONAL",
)


@dataclass(frozen=True)
class JanelaISE:
    nome: str
    inicio: datetime
    fim: datetime


def lista_sql_texto(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{valor}'" for valor in valores)


def tabela_existe(con: duckdb.DuckDBPyConnection, nome_tabela: str) -> bool:
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


def colunas_tabela(con: duckdb.DuckDBPyConnection, nome_tabela: str) -> set[str]:
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


def coluna_regional_disponivel(colunas: set[str]) -> str | None:
    for coluna in COLUNAS_REGIONAL:
        if coluna.upper() in colunas:
            return coluna
    return None


def regionais_disponiveis(db_path: str | Path) -> list[str]:
    with duckdb.connect(str(db_path), read_only=True) as con:
        if not tabela_existe(con, "gold_apuracao_uc"):
            return []

        colunas = colunas_tabela(con, "gold_apuracao_uc")
        regional = coluna_regional_disponivel(colunas)
        if not regional:
            return []

        rows = con.execute(
            f"""
            SELECT DISTINCT NULLIF(TRIM(CAST({regional} AS VARCHAR)), '') AS REGIONAL
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST({regional} AS VARCHAR)), '') IS NOT NULL
            ORDER BY REGIONAL
            """
        ).fetchall()

    return [row[0] for row in rows]


def validar_janelas(janelas: list[JanelaISE]) -> None:
    if not janelas:
        raise ValueError("Informe pelo menos uma janela ISE.")

    ordenadas = sorted(janelas, key=lambda janela: janela.inicio)
    for janela in ordenadas:
        if janela.fim <= janela.inicio:
            raise ValueError(f"Janela {janela.nome} possui fim menor ou igual ao inicio.")

    for anterior, atual in zip(ordenadas, ordenadas[1:]):
        if atual.inicio < anterior.fim:
            raise ValueError(
                f"As janelas {anterior.nome} e {atual.nome} se sobrepoem. "
                "Ajuste as datas para evitar dupla contagem."
            )


def cte_janelas(janelas: list[JanelaISE]) -> str:
    valores = []
    for indice, janela in enumerate(janelas, start=1):
        nome = janela.nome.replace("'", "''").strip() or f"Janela {indice}"
        inicio = janela.inicio.strftime("%Y-%m-%d %H:%M:%S")
        fim = janela.fim.strftime("%Y-%m-%d %H:%M:%S")
        valores.append(f"('{nome}', TIMESTAMP '{inicio}', TIMESTAMP '{fim}')")

    return ",\n                ".join(valores)


def expressao_texto(colunas: set[str], nome_coluna: str, padrao: str) -> str:
    if nome_coluna.upper() in colunas:
        return f"NULLIF(TRIM(CAST({nome_coluna} AS VARCHAR)), '')"
    return padrao


def montar_sql_simulacao(
    colunas: set[str],
    janelas: list[JanelaISE],
    regional: str | None,
    periodo_inicio: datetime,
    periodo_fim: datetime,
) -> str:
    regional_coluna = coluna_regional_disponivel(colunas)
    regional_expr = (
        f"NULLIF(TRIM(CAST({regional_coluna} AS VARCHAR)), '')"
        if regional_coluna
        else "'SEM_REGIONAL'"
    )
    filtro_regional = ""
    if regional and regional != "Todas" and regional_coluna:
        regional_sql = regional.replace("'", "''")
        filtro_regional = f"AND {regional_expr} = '{regional_sql}'"

    periodo_inicio_sql = periodo_inicio.strftime("%Y-%m-%d %H:%M:%S")
    periodo_fim_sql = periodo_fim.strftime("%Y-%m-%d %H:%M:%S")
    causa = "NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), '')"
    uc = "NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')"
    num_ocorrencia = expressao_texto(colunas, "NUM_OCORRENCIA_ADMS", "NULL")
    num_seq_intrp = expressao_texto(colunas, "NUM_SEQ_INTRP", "NULL")

    sigla_tiqs_dic = (
        "COALESCE(NULLIF(TRIM(CAST(SIGLA_TIQS_DIC AS VARCHAR)), ''), 'DIC_')"
        if "SIGLA_TIQS_DIC" in colunas
        else "'DIC_'"
    )
    sigla_reid_dic = expressao_texto(colunas, "SIGLA_REID_DIC", "NULL")
    sigla_tiqs_fic = (
        "COALESCE(NULLIF(TRIM(CAST(SIGLA_TIQS_FIC AS VARCHAR)), ''), 'FIC_')"
        if "SIGLA_TIQS_FIC" in colunas
        else "'FIC_'"
    )
    sigla_reid_fic = expressao_texto(colunas, "SIGLA_REID_FIC", "NULL")

    causa_ise = f"{causa} IN ({lista_sql_texto(CAUSAS_ISE)})"
    dic_bruto = (
        f"SUBSTR({sigla_tiqs_dic}, 1, 4) = 'DIC_' "
        f"AND COALESCE({sigla_reid_dic}, 'X') NOT IN ({lista_sql_texto(REGRAS_EXPURGO_DIC_BRUTO)})"
    )
    dic_liquido = f"SUBSTR({sigla_tiqs_dic}, 1, 4) = 'DIC_' AND {sigla_reid_dic} IS NULL"
    fic_bruto = (
        f"SUBSTR({sigla_tiqs_fic}, 1, 4) = 'FIC_' "
        f"AND COALESCE({sigla_reid_fic}, 'X') NOT IN ({lista_sql_texto(REGRAS_EXPURGO_FIC_BRUTO)})"
    )
    fic_liquido = f"SUBSTR({sigla_tiqs_fic}, 1, 4) = 'FIC_' AND {sigla_reid_fic} IS NULL"

    return f"""
        WITH janelas(NOME_JANELA, INICIO_JANELA, FIM_JANELA) AS (
            VALUES
                {cte_janelas(janelas)}
        ),
        base AS (
            SELECT
                j.NOME_JANELA,
                j.INICIO_JANELA,
                j.FIM_JANELA,
                {regional_expr} AS REGIONAL,
                {uc} AS UC,
                {num_ocorrencia} AS NUM_OCORRENCIA_ADMS,
                {num_seq_intrp} AS NUM_SEQ_INTRP,
                {causa} AS COD_CAUSA_INTRP,
                GREATEST(
                    0,
                    DATE_DIFF(
                        'second',
                        GREATEST(a.DTHR_INICIO_INTRP_UC, j.INICIO_JANELA),
                        LEAST(a.DATA_HORA_FIM_INTRP, j.FIM_JANELA)
                    ) / 3600.0
                ) AS DURACAO_JANELA_HORA,
                CASE WHEN {causa_ise} THEN 'S' ELSE 'N' END AS ISE_CAUSA_ELEGIVEL,
                CASE WHEN {causa_ise} AND {dic_bruto} THEN 1 ELSE 0 END AS FLAG_DIC_BRUTO,
                CASE WHEN {causa_ise} AND {dic_liquido} THEN 1 ELSE 0 END AS FLAG_DIC_LIQUIDO,
                CASE WHEN {causa_ise} AND {fic_bruto} THEN 1 ELSE 0 END AS FLAG_FIC_BRUTO,
                CASE WHEN {causa_ise} AND {fic_liquido} THEN 1 ELSE 0 END AS FLAG_FIC_LIQUIDO
            FROM gold_apuracao_uc a
            JOIN janelas j
              ON a.DTHR_INICIO_INTRP_UC < j.FIM_JANELA
             AND a.DATA_HORA_FIM_INTRP > j.INICIO_JANELA
            WHERE {uc} IS NOT NULL
              AND a.DTHR_INICIO_INTRP_UC < TIMESTAMP '{periodo_fim_sql}'
              AND a.DATA_HORA_FIM_INTRP >= TIMESTAMP '{periodo_inicio_sql}'
              {filtro_regional}
        )
        SELECT
            NOME_JANELA,
            REGIONAL,
            UC,
            CASE
                WHEN SUM(CASE WHEN FLAG_DIC_BRUTO = 1 THEN DURACAO_JANELA_HORA ELSE 0 END) > 0
                  OR SUM(CASE WHEN FLAG_FIC_BRUTO = 1 THEN 1 ELSE 0 END) > 0
                THEN 'S'
                ELSE 'N'
            END AS ISE_POTENCIAL,
            CASE
                WHEN SUM(CASE WHEN FLAG_DIC_LIQUIDO = 1 THEN DURACAO_JANELA_HORA ELSE 0 END) > 0
                  OR SUM(CASE WHEN FLAG_FIC_LIQUIDO = 1 THEN 1 ELSE 0 END) > 0
                THEN 'S'
                ELSE 'N'
            END AS ISE_RECLASSIFICAVEL,
            COUNT(*) AS EVENTOS_NA_JANELA,
            SUM(CASE WHEN ISE_CAUSA_ELEGIVEL = 'S' THEN 1 ELSE 0 END) AS EVENTOS_CAUSA_ISE,
            COUNT(DISTINCT CASE WHEN ISE_CAUSA_ELEGIVEL = 'S' THEN NUM_OCORRENCIA_ADMS END) AS OCORRENCIAS_CAUSA_ISE,
            SUM(CASE WHEN FLAG_FIC_BRUTO = 1 THEN 1 ELSE 0 END) AS ISE_CI_BRUTO_REFERENCIA,
            SUM(CASE WHEN FLAG_FIC_LIQUIDO = 1 THEN 1 ELSE 0 END) AS ISE_CI_LIQUIDO_RECLASSIFICAVEL,
            SUM(CASE WHEN FLAG_DIC_BRUTO = 1 THEN DURACAO_JANELA_HORA ELSE 0 END) AS ISE_CHI_BRUTO_REFERENCIA,
            SUM(CASE WHEN FLAG_DIC_LIQUIDO = 1 THEN DURACAO_JANELA_HORA ELSE 0 END) AS ISE_CHI_LIQUIDO_RECLASSIFICAVEL,
            MAX(CASE WHEN FLAG_DIC_BRUTO = 1 THEN DURACAO_JANELA_HORA ELSE 0 END) AS ISE_DMIC_BRUTO_REFERENCIA,
            MAX(CASE WHEN FLAG_DIC_LIQUIDO = 1 THEN DURACAO_JANELA_HORA ELSE 0 END) AS ISE_DMIC_LIQUIDO_RECLASSIFICAVEL,
            STRING_AGG(DISTINCT COD_CAUSA_INTRP, ', ' ORDER BY COD_CAUSA_INTRP) FILTER (
                WHERE ISE_CAUSA_ELEGIVEL = 'S'
            ) AS COD_CAUSAS_ISE
        FROM base
        GROUP BY
            NOME_JANELA,
            REGIONAL,
            UC
        HAVING ISE_POTENCIAL = 'S'
            OR ISE_RECLASSIFICAVEL = 'S'
        ORDER BY
            NOME_JANELA,
            ISE_CHI_BRUTO_REFERENCIA DESC,
            ISE_CHI_LIQUIDO_RECLASSIFICAVEL DESC,
            UC
    """


def calcular_simulacao_ise_por_janela(
    db_path: str | Path,
    janelas: list[JanelaISE],
    regional: str | None,
    periodo_inicio: datetime,
    periodo_fim: datetime,
) -> pd.DataFrame:
    validar_janelas(janelas)
    if periodo_fim <= periodo_inicio:
        raise ValueError("Periodo final deve ser maior que o periodo inicial.")

    with duckdb.connect(str(db_path), read_only=True) as con:
        if not tabela_existe(con, "gold_apuracao_uc"):
            raise RuntimeError("Tabela gold_apuracao_uc nao encontrada. Execute run.bat apuracao_parcial.")

        colunas = colunas_tabela(con, "gold_apuracao_uc")
        obrigatorias = {
            "NUM_UC_UCI",
            "COD_CAUSA_INTRP",
            "DTHR_INICIO_INTRP_UC",
            "DATA_HORA_FIM_INTRP",
        }
        faltantes = sorted(obrigatorias - colunas)
        if faltantes:
            raise RuntimeError(f"Colunas obrigatorias ausentes: {', '.join(faltantes)}")

        sql = montar_sql_simulacao(colunas, janelas, regional, periodo_inicio, periodo_fim)
        return con.execute(sql).fetchdf()


def resumo_simulacao(df: pd.DataFrame) -> dict[str, float]:
    if df.empty:
        return {
            "ucs": 0,
            "ucs_potencial": 0,
            "ucs_reclassificavel": 0,
            "chi_bruto": 0.0,
            "chi_liquido": 0.0,
            "ci_bruto": 0.0,
            "ci_liquido": 0.0,
        }

    return {
        "ucs": float(df["UC"].nunique()),
        "ucs_potencial": float(df.loc[df["ISE_POTENCIAL"] == "S", "UC"].nunique()),
        "ucs_reclassificavel": float(df.loc[df["ISE_RECLASSIFICAVEL"] == "S", "UC"].nunique()),
        "chi_bruto": float(df["ISE_CHI_BRUTO_REFERENCIA"].sum()),
        "chi_liquido": float(df["ISE_CHI_LIQUIDO_RECLASSIFICAVEL"].sum()),
        "ci_bruto": float(df["ISE_CI_BRUTO_REFERENCIA"].sum()),
        "ci_liquido": float(df["ISE_CI_LIQUIDO_RECLASSIFICAVEL"].sum()),
    }

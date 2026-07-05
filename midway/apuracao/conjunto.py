from __future__ import annotations

from pathlib import Path

from midway.apuracao.duckdb_utils import normalizar_linhas_unix, sql_literal, tabela_local_existe


def criar_gold_impacto_conjunto_dia(con) -> None:
    print("Criando gold_impacto_conjunto_dia...")

    if not tabela_local_existe(con, "gold_apuracao_uc"):
        raise RuntimeError("Tabela gold_apuracao_uc nao encontrada.")
    if not tabela_local_existe(con, "gold_metas_uc"):
        raise RuntimeError("Tabela gold_metas_uc nao encontrada.")

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_impacto_conjunto_dia AS
        WITH metas_uc AS (
            SELECT
                TRIM(CAST(ISN_UC AS VARCHAR)) AS UC,
                TRIM(CAST(COD_CONJUNTO_ANEEL AS VARCHAR)) AS COD_CONJUNTO_ANEEL,
                TRY_CAST(META_DEC AS DOUBLE) AS META_DEC,
                TRY_CAST(META_FEC AS DOUBLE) AS META_FEC
            FROM gold_metas_uc
            WHERE NULLIF(TRIM(CAST(ISN_UC AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_CONJUNTO_ANEEL AS VARCHAR)), '') IS NOT NULL
        ),
        conjunto_meta AS (
            SELECT
                COD_CONJUNTO_ANEEL,
                COUNT(DISTINCT UC) AS TOTAL_UCS_CONJUNTO,
                MAX(META_DEC) AS META_DEC_CONJUNTO,
                MAX(META_FEC) AS META_FEC_CONJUNTO
            FROM metas_uc
            GROUP BY COD_CONJUNTO_ANEEL
        ),
        apuracao AS (
            SELECT
                CAST(a.DATA_HORA_INIC_INTRP AS DATE) AS DATA_OCORRENCIA,
                COALESCE(
                    NULLIF(TRIM(CAST(a.COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), ''),
                    m.COD_CONJUNTO_ANEEL,
                    'SEM_CONJUNTO'
                ) AS COD_CONJUNTO_ANEEL,
                a.REGIONAL,
                a.NUM_OCORRENCIA_ADMS,
                a.NUM_SEQ_INTRP,
                TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)) AS UC,
                a.CI_LIQUIDO,
                a.CHI_LIQUIDO,
                a.DURACAO_HORA
            FROM gold_apuracao_uc a
            LEFT JOIN metas_uc m
              ON m.UC = TRIM(CAST(a.NUM_UC_UCI AS VARCHAR))
            WHERE a.DATA_HORA_INIC_INTRP IS NOT NULL
              AND COALESCE(a.CI_LIQUIDO, 0) + COALESCE(a.CHI_LIQUIDO, 0) > 0
        ),
        ocorrencia AS (
            SELECT
                DATA_OCORRENCIA,
                COD_CONJUNTO_ANEEL,
                REGIONAL,
                NUM_OCORRENCIA_ADMS,
                COUNT(*) AS LINHAS_UC,
                COUNT(DISTINCT NUM_SEQ_INTRP) AS QTD_INTERRUPCOES,
                COUNT(DISTINCT UC) AS QTD_UCS_AFETADAS,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS FIC_IMPACTO,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS DIC_IMPACTO,
                MAX(COALESCE(DURACAO_HORA, 0)) AS MAX_DURACAO_H
            FROM apuracao
            GROUP BY
                DATA_OCORRENCIA,
                COD_CONJUNTO_ANEEL,
                REGIONAL,
                NUM_OCORRENCIA_ADMS
        )
        SELECT
            o.DATA_OCORRENCIA,
            o.COD_CONJUNTO_ANEEL,
            o.REGIONAL,
            o.NUM_OCORRENCIA_ADMS,
            o.LINHAS_UC,
            o.QTD_INTERRUPCOES,
            o.QTD_UCS_AFETADAS,
            o.FIC_IMPACTO,
            o.DIC_IMPACTO,
            o.MAX_DURACAO_H,
            COALESCE(c.TOTAL_UCS_CONJUNTO, 0) AS TOTAL_UCS_CONJUNTO,
            c.META_DEC_CONJUNTO,
            c.META_FEC_CONJUNTO,
            CASE
                WHEN COALESCE(c.TOTAL_UCS_CONJUNTO, 0) > 0
                THEN o.DIC_IMPACTO / c.TOTAL_UCS_CONJUNTO
                ELSE NULL
            END AS DEC_IMPACTO_CONJUNTO,
            CASE
                WHEN COALESCE(c.TOTAL_UCS_CONJUNTO, 0) > 0
                THEN o.FIC_IMPACTO / c.TOTAL_UCS_CONJUNTO
                ELSE NULL
            END AS FEC_IMPACTO_CONJUNTO,
            CASE
                WHEN COALESCE(c.TOTAL_UCS_CONJUNTO, 0) > 0
                 AND COALESCE(c.META_DEC_CONJUNTO, 0) > 0
                THEN (o.DIC_IMPACTO / c.TOTAL_UCS_CONJUNTO) / c.META_DEC_CONJUNTO * 100
                ELSE NULL
            END AS PCT_META_DEC_CONSUMIDA,
            CASE
                WHEN COALESCE(c.TOTAL_UCS_CONJUNTO, 0) > 0
                 AND COALESCE(c.META_FEC_CONJUNTO, 0) > 0
                THEN (o.FIC_IMPACTO / c.TOTAL_UCS_CONJUNTO) / c.META_FEC_CONJUNTO * 100
                ELSE NULL
            END AS PCT_META_FEC_CONSUMIDA,
            GREATEST(
                COALESCE(
                    CASE
                        WHEN COALESCE(c.TOTAL_UCS_CONJUNTO, 0) > 0
                         AND COALESCE(c.META_DEC_CONJUNTO, 0) > 0
                        THEN (o.DIC_IMPACTO / c.TOTAL_UCS_CONJUNTO) / c.META_DEC_CONJUNTO * 100
                    END,
                    0
                ),
                COALESCE(
                    CASE
                        WHEN COALESCE(c.TOTAL_UCS_CONJUNTO, 0) > 0
                         AND COALESCE(c.META_FEC_CONJUNTO, 0) > 0
                        THEN (o.FIC_IMPACTO / c.TOTAL_UCS_CONJUNTO) / c.META_FEC_CONJUNTO * 100
                    END,
                    0
                )
            ) AS PCT_META_MAX_CONSUMIDA
        FROM ocorrencia o
        LEFT JOIN conjunto_meta c
          ON c.COD_CONJUNTO_ANEEL = o.COD_CONJUNTO_ANEEL
        """
    )


def criar_gold_meta_dia_critico_conjunto(con) -> None:
    print("Criando gold_meta_dia_critico_conjunto...")

    if not tabela_local_existe(con, "gold_metas_uc"):
        raise RuntimeError("Tabela gold_metas_uc nao encontrada.")

    con.execute(
        """
        CREATE OR REPLACE TABLE gold_meta_dia_critico_conjunto AS
        WITH metas_urbanas AS (
            SELECT
                TRIM(CAST(COD_CONJUNTO_ANEEL AS VARCHAR)) AS COD_CONJUNTO_ANEEL,
                TRIM(CAST(ISN_UC AS VARCHAR)) AS UC,
                TRY_CAST(META_DICRI AS DOUBLE) AS META_DICRI
            FROM gold_metas_uc
            WHERE NULLIF(TRIM(CAST(COD_CONJUNTO_ANEEL AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(ISN_UC AS VARCHAR)), '') IS NOT NULL
              AND UPPER(TRIM(CAST(URB_RUR AS VARCHAR))) = 'U'
        ),
        conjunto AS (
            SELECT
                COD_CONJUNTO_ANEEL,
                COUNT(DISTINCT UC) AS QTD_UCS_URBANAS,
                MAX(META_DICRI) AS META_DICRI_UC_URBANA_REFERENCIA
            FROM metas_urbanas
            GROUP BY COD_CONJUNTO_ANEEL
        )
        SELECT
            COD_CONJUNTO_ANEEL,
            QTD_UCS_URBANAS,
            META_DICRI_UC_URBANA_REFERENCIA,
            1.5 AS FATOR_META_DIA_CRITICO_SINTETICA,
            META_DICRI_UC_URBANA_REFERENCIA * 1.5 AS META_DIA_CRITICO_SINTETICA,
            CAST(NULL AS DOUBLE) AS META_DIA_CRITICO_REAL,
            'SINTETICA_1_5_META_DICRI_UC_URBANA' AS TIPO_META_DIA_CRITICO,
            'S' AS PENDENCIA_META_REAL
        FROM conjunto
        WHERE COALESCE(META_DICRI_UC_URBANA_REFERENCIA, 0) > 0
        """
    )


def exportar_gold_impacto_conjunto_dia(
    con,
    *,
    marts_dir: Path,
    anomes: str,
    timestamp: str,
    processed_duckdb_path: Path,
) -> None:
    if not tabela_local_existe(con, "gold_impacto_conjunto_dia"):
        raise RuntimeError("Tabela gold_impacto_conjunto_dia nao encontrada.")

    caminho_csv = marts_dir / f"Gold_Impacto_Conjunto_Dia_{anomes}_{timestamp}.CSV"
    caminho_resumo = marts_dir / f"Gold_Impacto_Conjunto_Dia_{anomes}_{timestamp}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_impacto_conjunto_dia
            ORDER BY
                PCT_META_MAX_CONSUMIDA DESC,
                DATA_OCORRENCIA DESC,
                DIC_IMPACTO DESC,
                FIC_IMPACTO DESC
            LIMIT 50000
        )
        TO {sql_literal(caminho_csv.as_posix())}
        WITH (
            HEADER TRUE,
            DELIMITER '|',
            NULL ''
        )
        """
    )
    normalizar_linhas_unix(caminho_csv)

    resumo = con.execute(
        """
        SELECT
            COUNT(*) AS OCORRENCIAS_DIA_CONJUNTO,
            COUNT(DISTINCT COD_CONJUNTO_ANEEL) AS CONJUNTOS,
            COUNT(DISTINCT DATA_OCORRENCIA) AS DIAS,
            MAX(PCT_META_MAX_CONSUMIDA) AS MAIOR_PCT_META,
            SUM(DIC_IMPACTO) AS DIC_TOTAL,
            SUM(FIC_IMPACTO) AS FIC_TOTAL
        FROM gold_impacto_conjunto_dia
        """
    ).fetchone()

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("GOLD IMPACTO CONJUNTO DIA\n")
        arquivo.write(f"ANOMES: {anomes}\n")
        arquivo.write(f"DuckDB processado: {processed_duckdb_path}\n")
        arquivo.write(f"Ocorrencias/dia/conjunto: {resumo[0]}\n")
        arquivo.write(f"Conjuntos avaliados: {resumo[1]}\n")
        arquivo.write(f"Dias avaliados: {resumo[2]}\n")
        arquivo.write(f"Maior percentual de meta consumida: {resumo[3]}\n")
        arquivo.write(f"DIC impacto total: {resumo[4]}\n")
        arquivo.write(f"FIC impacto total: {resumo[5]}\n")
        arquivo.write(f"Arquivo: {caminho_csv}\n")

    print(f"gold_impacto_conjunto_dia criada. Registros: {resumo[0]:,}")
    print(f"Conferencia impacto conjunto/dia: {caminho_csv}")


def exportar_gold_meta_dia_critico_conjunto(
    con,
    *,
    marts_dir: Path,
    anomes: str,
    timestamp: str,
    processed_duckdb_path: Path,
) -> None:
    if not tabela_local_existe(con, "gold_meta_dia_critico_conjunto"):
        raise RuntimeError("Tabela gold_meta_dia_critico_conjunto nao encontrada.")

    caminho_csv = marts_dir / f"Gold_Meta_Dia_Critico_Conjunto_{anomes}_{timestamp}.CSV"
    caminho_resumo = marts_dir / f"Gold_Meta_Dia_Critico_Conjunto_{anomes}_{timestamp}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM gold_meta_dia_critico_conjunto
            ORDER BY COD_CONJUNTO_ANEEL
        )
        TO {sql_literal(caminho_csv.as_posix())}
        WITH (
            HEADER TRUE,
            DELIMITER '|',
            NULL ''
        )
        """
    )
    normalizar_linhas_unix(caminho_csv)

    resumo = con.execute(
        """
        SELECT
            COUNT(*) AS CONJUNTOS,
            SUM(QTD_UCS_URBANAS) AS UCS_URBANAS,
            MIN(META_DIA_CRITICO_SINTETICA) AS MENOR_META_SINTETICA,
            MAX(META_DIA_CRITICO_SINTETICA) AS MAIOR_META_SINTETICA,
            SUM(CASE WHEN META_DIA_CRITICO_REAL IS NULL THEN 1 ELSE 0 END) AS METAS_REAIS_PENDENTES
        FROM gold_meta_dia_critico_conjunto
        """
    ).fetchone()

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("GOLD META DIA CRITICO CONJUNTO\n")
        arquivo.write(f"ANOMES: {anomes}\n")
        arquivo.write(f"DuckDB processado: {processed_duckdb_path}\n")
        arquivo.write("Criterio sintetico: 1.5 * MAX(META_DICRI) das UCs urbanas do conjunto\n")
        arquivo.write("Pendencia: substituir por meta real de dia critico por conjunto quando disponivel\n")
        arquivo.write(f"Conjuntos: {resumo[0]}\n")
        arquivo.write(f"UCs urbanas: {resumo[1]}\n")
        arquivo.write(f"Menor meta sintetica: {resumo[2]}\n")
        arquivo.write(f"Maior meta sintetica: {resumo[3]}\n")
        arquivo.write(f"Metas reais pendentes: {resumo[4]}\n")
        arquivo.write(f"Arquivo: {caminho_csv}\n")

    print(f"gold_meta_dia_critico_conjunto criada. Registros: {resumo[0]:,}")
    print(f"Conferencia meta dia critico/conjunto: {caminho_csv}")

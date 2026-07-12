from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import duckdb


CACHE_TABLE = "gold_analise_tecnica_impacto_base"


BASE_SOURCE_SQL = """
WITH apuracao AS (
    SELECT
        TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
        COUNT(*) AS QTD_LINHAS_APURACAO,
        COUNT(DISTINCT TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))) AS QTD_INTERRUPCOES,
        COUNT(DISTINCT TRIM(CAST(NUM_UC_UCI AS VARCHAR))) AS QTD_UCS,
        MIN(DATA_HORA_INIC_INTRP) AS PRIMEIRO_INICIO,
        MAX(DATA_HORA_FIM_INTRP) AS ULTIMO_FIM,
        SUM(COALESCE(CHI_BRUTO, 0)) AS CHI_BRUTO,
        SUM(COALESCE(CI_BRUTO, 0)) AS CI_BRUTO,
        SUM(COALESCE(CHI_LIQUIDO, 0)) AS CHI_LIQUIDO,
        SUM(COALESCE(CI_LIQUIDO, 0)) AS CI_LIQUIDO,
        MAX(COALESCE(DURACAO_HORA, 0)) AS DURACAO_MAX_HORA
    FROM gold_apuracao_uc
    WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
    GROUP BY TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR))
),
classificacao AS (
    SELECT
        TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
        COUNT(DISTINCT TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) || '/' || LPAD(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), 2, '0')) AS QTD_PARES_COMP_CAUSA,
        STRING_AGG(
            DISTINCT TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) || '/' || LPAD(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), 2, '0'),
            ', '
        ) AS PARES_COMPONENTE_CAUSA,
        MAX(CASE
            WHEN TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) = '92'
             AND LPAD(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), 2, '0') = '82'
            THEN 1 ELSE 0 END
        ) AS TEM_9282,
        MODE(TRIM(CAST(COD_COMP_INTRP AS VARCHAR))) AS COD_COMP_PRINCIPAL,
        MODE(LPAD(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), 2, '0')) AS COD_CAUSA_PRINCIPAL,
        MODE(TRIM(CAST(COD_GRUPO_COMP_INTRP AS VARCHAR))) AS COD_GRUPO_PRINCIPAL
    FROM gold_interrupcao_tratada
    WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
    GROUP BY TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR))
),
validacao_comp_causa AS (
    SELECT
        TRIM(CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
        COUNT(DISTINCT CASE
            WHEN ref.CHAVE_COMP_CAUSA IS NULL
            THEN TRIM(CAST(a.COD_GRUPO_COMP_INTRP AS VARCHAR)) || '/'
              || TRIM(CAST(a.COD_COMP_INTRP AS VARCHAR)) || '/'
              || LPAD(TRIM(CAST(a.COD_CAUSA_INTRP AS VARCHAR)), 2, '0')
        END) AS QTD_VIOLACAO_COMP_CAUSA,
        STRING_AGG(
            DISTINCT CASE
                WHEN ref.CHAVE_COMP_CAUSA IS NULL
                THEN TRIM(CAST(a.COD_GRUPO_COMP_INTRP AS VARCHAR)) || '/'
                  || TRIM(CAST(a.COD_COMP_INTRP AS VARCHAR)) || '/'
                  || LPAD(TRIM(CAST(a.COD_CAUSA_INTRP AS VARCHAR)), 2, '0')
            END,
            ', '
        ) AS VIOLACOES_COMPONENTE_CAUSA
    FROM gold_interrupcao_tratada a
    LEFT JOIN gold_iqs_referencia_componente_causa ref
      ON TRIM(CAST(a.COD_GRUPO_COMP_INTRP AS VARCHAR)) = TRIM(CAST(ref.COD_GRUPO_GCR AS VARCHAR))
     AND TRIM(CAST(a.COD_COMP_INTRP AS VARCHAR)) = TRIM(CAST(ref.COD_COMP AS VARCHAR))
     AND LPAD(TRIM(CAST(a.COD_CAUSA_INTRP AS VARCHAR)), 2, '0') = LPAD(TRIM(CAST(ref.COD_CAUSA AS VARCHAR)), 2, '0')
    WHERE NULLIF(TRIM(CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
    GROUP BY TRIM(CAST(a.NUM_OCORRENCIA_ADMS AS VARCHAR))
),
ressarcimento AS (
    SELECT
        u.NUM_OCORRENCIA_ADMS,
        SUM(COALESCE(r.COMP_TOTAL_PRODIST, 0)) AS RESSARCIMENTO_ESTIMADO,
        COUNT(DISTINCT CASE WHEN COALESCE(r.COMP_TOTAL_PRODIST, 0) > 0 THEN u.NUM_UC_UCI END) AS QTD_UCS_RESSARCIMENTO
    FROM (
        SELECT DISTINCT
            TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
            TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS NUM_UC_UCI
        FROM gold_apuracao_uc
        WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
          AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
    ) u
    LEFT JOIN gold_ressarcimento_prodist r
      ON u.NUM_UC_UCI = TRIM(CAST(r.UC AS VARCHAR))
    GROUP BY u.NUM_OCORRENCIA_ADMS
),
reclamacoes AS (
    SELECT
        NUM_OCORRENCIA_ADMS,
        QTD_RECLAMACOES,
        MAX_SCORE_VINCULO_RECLAMACAO,
        TIPOS_RECLAMACAO_PROVAVEIS,
        CAUSAS_PROVAVEIS_RECLAMACAO,
        GRUPOS_COMPONENTE_IQS,
        GRUPOS_CAUSA_IQS
    FROM gold_reclamacao_ocorrencia_resumo
)
SELECT
    a.NUM_OCORRENCIA_ADMS,
    a.QTD_LINHAS_APURACAO,
    a.QTD_INTERRUPCOES,
    a.QTD_UCS,
    a.PRIMEIRO_INICIO,
    a.ULTIMO_FIM,
    a.CHI_BRUTO,
    a.CI_BRUTO,
    a.CHI_LIQUIDO,
    a.CI_LIQUIDO,
    a.DURACAO_MAX_HORA,
    COALESCE(c.QTD_PARES_COMP_CAUSA, 0) AS QTD_PARES_COMP_CAUSA,
    c.PARES_COMPONENTE_CAUSA,
    COALESCE(c.TEM_9282, 0) AS TEM_9282,
    c.COD_COMP_PRINCIPAL,
    c.COD_CAUSA_PRINCIPAL,
    c.COD_GRUPO_PRINCIPAL,
    COALESCE(v.QTD_VIOLACAO_COMP_CAUSA, 0) AS QTD_VIOLACAO_COMP_CAUSA,
    v.VIOLACOES_COMPONENTE_CAUSA,
    COALESCE(rs.RESSARCIMENTO_ESTIMADO, 0) AS RESSARCIMENTO_ESTIMADO,
    COALESCE(rs.QTD_UCS_RESSARCIMENTO, 0) AS QTD_UCS_RESSARCIMENTO,
    COALESCE(r.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
    COALESCE(r.MAX_SCORE_VINCULO_RECLAMACAO, 0) AS MAX_SCORE_RECLAMACAO,
    r.TIPOS_RECLAMACAO_PROVAVEIS,
    r.CAUSAS_PROVAVEIS_RECLAMACAO,
    r.GRUPOS_COMPONENTE_IQS,
    r.GRUPOS_CAUSA_IQS
FROM apuracao a
LEFT JOIN classificacao c
  ON a.NUM_OCORRENCIA_ADMS = c.NUM_OCORRENCIA_ADMS
LEFT JOIN validacao_comp_causa v
  ON a.NUM_OCORRENCIA_ADMS = v.NUM_OCORRENCIA_ADMS
LEFT JOIN ressarcimento rs
  ON a.NUM_OCORRENCIA_ADMS = rs.NUM_OCORRENCIA_ADMS
LEFT JOIN reclamacoes r
  ON a.NUM_OCORRENCIA_ADMS = r.NUM_OCORRENCIA_ADMS
"""


def processed_path(anomes: str) -> Path:
    return Path("data/processed") / f"iqs_adms_processed_{anomes}.duckdb"


def cache_exists(con: duckdb.DuckDBPyConnection, table_name: str = CACHE_TABLE) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


def source_sql(con: duckdb.DuckDBPyConnection) -> tuple[str, bool]:
    if cache_exists(con):
        return f"SELECT * FROM {CACHE_TABLE}", True
    return BASE_SOURCE_SQL, False


def materializar_cache(anomes: str, force: bool = True) -> dict[str, object]:
    db_path = processed_path(anomes)
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB processado não encontrado: {db_path}")

    started = time.perf_counter()
    with duckdb.connect(str(db_path), read_only=False) as con:
        if force:
            con.execute(f"DROP TABLE IF EXISTS {CACHE_TABLE}")
        con.execute(f"CREATE TABLE IF NOT EXISTS {CACHE_TABLE} AS {BASE_SOURCE_SQL}")
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{CACHE_TABLE}_ocorrencia ON {CACHE_TABLE}(NUM_OCORRENCIA_ADMS)")
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{CACHE_TABLE}_impacto ON {CACHE_TABLE}(CHI_LIQUIDO, CI_LIQUIDO)")
        row_count = con.execute(f"SELECT COUNT(*) FROM {CACHE_TABLE}").fetchone()[0]
    elapsed = time.perf_counter() - started
    return {
        "anomes": anomes,
        "duckdb": str(db_path),
        "tabela": CACHE_TABLE,
        "registros": row_count,
        "segundos": round(elapsed, 3),
    }


def main() -> None:
    anomes = sys.argv[1] if len(sys.argv) > 1 else os.getenv("ANOMES", "202606")
    resultado = materializar_cache(anomes=anomes, force=True)
    print("CACHE ANALISE TECNICA")
    for chave, valor in resultado.items():
        print(f"{chave}: {valor}")


if __name__ == "__main__":
    main()

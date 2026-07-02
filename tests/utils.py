import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
PROCESSED_DUCKDB_PATH = Path("data") / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
TOLERANCIA_DECIMAL = 0.001


def conectar():
    if not PROCESSED_DUCKDB_PATH.exists():
        raise AssertionError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")
    return duckdb.connect(str(PROCESSED_DUCKDB_PATH), read_only=True)


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


def coluna_existe(con, nome_tabela: str, nome_coluna: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = ?
              AND column_name = ?
            """,
            [nome_tabela, nome_coluna],
        ).fetchone()[0]
        > 0
    )


def escalar(con, sql: str):
    return con.execute(sql).fetchone()[0]

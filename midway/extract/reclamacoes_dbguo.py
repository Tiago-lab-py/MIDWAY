from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


load_dotenv(override=True)

def _anomes() -> str:
    return os.getenv("ANOMES", "202607")

DB_URL = os.getenv("DB_URL")
REEXTRAIR_DBGUO = os.getenv("REEXTRAIR_DBGUO", "0") == "1"

BASE_DIR = Path("data")
RAW_DIR = BASE_DIR / "raw"
MARTS_DIR = BASE_DIR / "marts"
SQL_PATH = Path("SQL") / "DBGUO_reclamacoes.sql"
RAW_TABLE = "raw_dbguo_reclamacoes"
TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")

def _raw_duckdb_path() -> Path:
    return RAW_DIR / f"dbguo_raw_{_anomes()}.duckdb"


def conectar_postgres():
    if not DB_URL:
        raise RuntimeError("Variavel DB_URL nao configurada no .env.")
    return create_engine(DB_URL)


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


def carregar_sql() -> str:
    if not SQL_PATH.exists():
        raise RuntimeError(f"SQL nao encontrado: {SQL_PATH}")

    sql = SQL_PATH.read_text(encoding="utf-8").strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    return sql


def exportar_amostra_e_resumo(con: duckdb.DuckDBPyConnection, total: int) -> None:
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    amostra_path = MARTS_DIR / f"DBGUO_Reclamacoes_{ANOMES}_{TIMESTAMP}_AMOSTRA.CSV"
    resumo_path = MARTS_DIR / f"DBGUO_Reclamacoes_{ANOMES}_{TIMESTAMP}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM {RAW_TABLE}
            LIMIT 100
        )
        TO '{amostra_path.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )

    total_validado = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
    with resumo_path.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("EXTRACAO DBGUO / RECLAMACOES\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write(f"SQL: {SQL_PATH}\n")
        arquivo.write(f"DuckDB raw: {RAW_DUCKDB_PATH}\n")
        arquivo.write(f"Tabela raw: {RAW_TABLE}\n")
        arquivo.write(f"Registros extraidos: {total}\n")
        arquivo.write(f"Registros validados: {total_validado}\n")
        arquivo.write(f"Amostra CSV: {amostra_path}\n")

    print(f"Amostra: {amostra_path}")
    print(f"Resumo: {resumo_path}")


def criar_indices(con: duckdb.DuckDBPyConnection) -> None:
    colunas = {
        row[1].upper()
        for row in con.execute(f"PRAGMA table_info('{RAW_TABLE}')").fetchall()
    }

    for coluna in ["NUM_UC", "UC", "UC_CONSUMIDORA", "NUM_UC_RECLAMACAO"]:
        if coluna.upper() not in colunas:
            continue

        con.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{RAW_TABLE}_{coluna.lower()} ON {RAW_TABLE}({coluna})"
        )
        print(f"Indice criado em {coluna}.")
        return

    print("Nenhuma coluna de UC encontrada para indice.")


def extrair_reclamacoes_dbguo(chunksize: int = 100_000) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MARTS_DIR.mkdir(parents=True, exist_ok=True)

    sql = carregar_sql()

    raw_db = _raw_duckdb_path()
    anomes_val = _anomes()
    print(f"Extraindo reclamacoes DBGUO ANOMES={anomes_val}...")
    print(f"SQL: {SQL_PATH}")
    print(f"DuckDB destino: {raw_db}")

    con_duck = duckdb.connect(str(raw_db))
    try:
        if tabela_existe(con_duck, RAW_TABLE) and not REEXTRAIR_DBGUO:
            total_existente = con_duck.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
            print(f"Tabela {RAW_TABLE} ja existe.")
            print(f"Registros existentes: {total_existente:,}")
            print("Defina REEXTRAIR_DBGUO=1 para extrair novamente.")
            return

        engine = conectar_postgres()
        primeiro_lote = True
        total = 0

        con_duck.execute(f"DROP TABLE IF EXISTS {RAW_TABLE}")

        with engine.connect() as con_pg:
            for df in pd.read_sql_query(
                text(sql),
                con_pg,
                params={"anomes": ANOMES},
                chunksize=chunksize,
            ):
                if df.empty:
                    continue

                df.columns = [col.upper() for col in df.columns]
                con_duck.register("dbguo_reclamacoes_lote_tmp", df)

                if primeiro_lote:
                    con_duck.execute(
                        f"CREATE TABLE {RAW_TABLE} AS SELECT * FROM dbguo_reclamacoes_lote_tmp"
                    )
                    primeiro_lote = False
                else:
                    con_duck.execute(f"INSERT INTO {RAW_TABLE} SELECT * FROM dbguo_reclamacoes_lote_tmp")

                con_duck.unregister("dbguo_reclamacoes_lote_tmp")
                total += len(df)
                print(f"Reclamacoes extraidas: {total:,}")

        if primeiro_lote:
            raise RuntimeError("Nenhum registro de reclamacao extraido.")

        criar_indices(con_duck)
        exportar_amostra_e_resumo(con_duck, total)
        print(f"Extracao DBGUO finalizada. Registros: {total:,}")
    finally:
        con_duck.close()


if __name__ == "__main__":
    extrair_reclamacoes_dbguo()
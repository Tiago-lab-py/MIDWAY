import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import oracledb
from dotenv import load_dotenv

from midway.transform.iqs_raw_utils import iqs_raw_path, materializar_gold_table, processed_path


load_dotenv(override=True)

IQS_UID = os.getenv("IQS_UID")
IQS_PWD = os.getenv("IQS_PWD")
IQS_DB = os.getenv("IQS_DB")
IQS_CONFIG_DIR = os.getenv("IQS_CONFIG_DIR")
ANOMES = os.getenv("ANOMES", "202606")
REEXTRAIR_METAS_UC = os.getenv("REEXTRAIR_METAS_UC", "0") == "1"

BASE_DIR = Path("data")
MARTS_DIR = BASE_DIR / "marts"
RAW_DIR = BASE_DIR / "raw"
SQL_PATH = Path("SQL") / "IQS_METAS UC 2026.sql"
IQS_RAW_DUCKDB_PATH = iqs_raw_path(ANOMES)
PROCESSED_DUCKDB_PATH = processed_path(ANOMES)
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")


def conectar_oracle():
    if IQS_CONFIG_DIR:
        os.environ["TNS_ADMIN"] = IQS_CONFIG_DIR
        oracledb.defaults.config_dir = IQS_CONFIG_DIR

    return oracledb.connect(
        user=IQS_UID,
        password=IQS_PWD,
        dsn=IQS_DB,
    )


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


def exportar_amostra(con, caminho_amostra: Path):
    con.execute(
        f"""
        COPY (
            SELECT *
            FROM raw_iqs_metas_uc
            LIMIT 100
        )
        TO '{caminho_amostra.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )


def extrair_metas_uc(chunksize: int = 100_000):
    if not SQL_PATH.exists():
        raise RuntimeError(f"SQL nao encontrado: {SQL_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    con_duck = duckdb.connect(str(IQS_RAW_DUCKDB_PATH))
    try:
        if tabela_existe(con_duck, "raw_iqs_metas_uc") and not REEXTRAIR_METAS_UC:
            total_existente = con_duck.execute("SELECT COUNT(*) FROM raw_iqs_metas_uc").fetchone()[0]
            print("Tabela raw_iqs_metas_uc ja existe.")
            print(f"Registros existentes: {total_existente:,}")
            print("Defina REEXTRAIR_METAS_UC=1 para extrair novamente.")
            materializar_gold_table(ANOMES, "raw_iqs_metas_uc", "gold_metas_uc")
            return

        print(f"Extraindo metas UC sob demanda ANOMES={ANOMES}...")
        print(f"SQL: {SQL_PATH}")
        print(f"DuckDB raw IQS destino: {IQS_RAW_DUCKDB_PATH}")

        sql = SQL_PATH.read_text(encoding="utf-8").strip()
        if sql.endswith(";"):
            sql = sql[:-1].strip()
        con_oracle = conectar_oracle()

        primeiro_lote = True
        total = 0

        try:
            con_duck.execute("DROP TABLE IF EXISTS raw_iqs_metas_uc")

            for df in pd.read_sql_query(sql, con_oracle, chunksize=chunksize):
                if df.empty:
                    continue

                df.columns = [col.upper() for col in df.columns]
                con_duck.register("metas_uc_lote_tmp", df)

                if primeiro_lote:
                    con_duck.execute("CREATE TABLE raw_iqs_metas_uc AS SELECT * FROM metas_uc_lote_tmp")
                    primeiro_lote = False
                else:
                    con_duck.execute("INSERT INTO raw_iqs_metas_uc SELECT * FROM metas_uc_lote_tmp")

                total += len(df)
                print(f"Metas UC extraidas: {total:,}")
        finally:
            con_oracle.close()

        if primeiro_lote:
            raise RuntimeError("Nenhum registro de metas UC extraido.")

        materializar_gold_table(ANOMES, "raw_iqs_metas_uc", "gold_metas_uc")

        total_validado = con_duck.execute("SELECT COUNT(*) FROM raw_iqs_metas_uc").fetchone()[0]
        caminho_resumo = MARTS_DIR / f"Metas_UC_IQS_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO.TXT"
        caminho_amostra = MARTS_DIR / f"Metas_UC_IQS_{ANOMES}_{TIMESTAMP_ARQ}_AMOSTRA.CSV"

        exportar_amostra(con_duck, caminho_amostra)

        with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write("EXTRACAO METAS UC IQS\n")
            arquivo.write(f"ANOMES: {ANOMES}\n")
            arquivo.write(f"SQL: {SQL_PATH}\n")
            arquivo.write(f"DuckDB raw IQS: {IQS_RAW_DUCKDB_PATH}\n")
            arquivo.write("Tabela raw: raw_iqs_metas_uc\n")
            arquivo.write("Tabela processada compatibilidade: gold_metas_uc\n")
            arquivo.write(f"Registros extraidos: {total_validado}\n")
            arquivo.write(f"Amostra CSV: {caminho_amostra}\n")

        print(f"Extracao metas UC finalizada. Registros: {total_validado:,}")
        print(f"Amostra: {caminho_amostra}")
        print(f"Resumo: {caminho_resumo}")
    finally:
        con_duck.close()


if __name__ == "__main__":
    extrair_metas_uc()

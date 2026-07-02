import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import oracledb
from dotenv import load_dotenv

from midway.transform.iqs_raw_utils import iqs_raw_path, materializar_gold_table, processed_path


load_dotenv()

IQS_UID = os.getenv("IQS_UID")
IQS_PWD = os.getenv("IQS_PWD")
IQS_DB = os.getenv("IQS_DB")
IQS_CONFIG_DIR = os.getenv("IQS_CONFIG_DIR")
ANOMES = os.getenv("ANOMES", "202606")
REEXTRAIR_VRC = os.getenv("REEXTRAIR_VRC", "0") == "1"

BASE_DIR = Path("data")
MARTS_DIR = BASE_DIR / "marts"
RAW_DIR = BASE_DIR / "raw"
SQL_PATH = Path("SQL") / "IQS_vrc.sql"
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


def extrair_vrc(chunksize: int = 100_000):
    if not SQL_PATH.exists():
        raise RuntimeError(f"SQL nao encontrado: {SQL_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    con_duck = duckdb.connect(str(IQS_RAW_DUCKDB_PATH))
    try:
        if tabela_existe(con_duck, "raw_iqs_vrc") and not REEXTRAIR_VRC:
            total_existente = con_duck.execute("SELECT COUNT(*) FROM raw_iqs_vrc").fetchone()[0]
            print("Tabela raw_iqs_vrc ja existe.")
            print(f"Registros existentes: {total_existente:,}")
            print("Defina REEXTRAIR_VRC=1 para extrair novamente.")
            materializar_gold_table(ANOMES, "raw_iqs_vrc", "gold_vrc")
            return

        print(f"Extraindo VRC sob demanda ANOMES={ANOMES}...")
        print(f"SQL: {SQL_PATH}")
        print(f"DuckDB raw IQS destino: {IQS_RAW_DUCKDB_PATH}")

        sql = SQL_PATH.read_text(encoding="utf-8")
        con_oracle = conectar_oracle()

        primeiro_lote = True
        total = 0
        soma_vrc = 0.0
        min_vrc = None
        max_vrc = None

        try:
            con_duck.execute("DROP TABLE IF EXISTS raw_iqs_vrc")

            for df in pd.read_sql_query(sql, con_oracle, chunksize=chunksize):
                if df.empty:
                    continue

                df.columns = [col.upper() for col in df.columns]
                con_duck.register("vrc_lote_tmp", df)

                if primeiro_lote:
                    con_duck.execute("CREATE TABLE raw_iqs_vrc AS SELECT * FROM vrc_lote_tmp")
                    primeiro_lote = False
                else:
                    con_duck.execute("INSERT INTO raw_iqs_vrc SELECT * FROM vrc_lote_tmp")

                total += len(df)
                if "VRC" in df.columns:
                    serie_vrc = pd.to_numeric(df["VRC"], errors="coerce").fillna(0)
                    soma_vrc += float(serie_vrc.sum())
                    lote_min = float(serie_vrc.min()) if not serie_vrc.empty else None
                    lote_max = float(serie_vrc.max()) if not serie_vrc.empty else None
                    min_vrc = lote_min if min_vrc is None else min(min_vrc, lote_min)
                    max_vrc = lote_max if max_vrc is None else max(max_vrc, lote_max)

                print(f"VRC extraidos: {total:,}")
        finally:
            con_oracle.close()

        if primeiro_lote:
            raise RuntimeError("Nenhum registro VRC extraido.")

        con_duck.execute("CREATE INDEX IF NOT EXISTS idx_raw_iqs_vrc_uc ON raw_iqs_vrc(ISN_UC)")
        materializar_gold_table(ANOMES, "raw_iqs_vrc", "gold_vrc")
        con_processed = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
        try:
            con_processed.execute("CREATE INDEX IF NOT EXISTS idx_gold_vrc_uc ON gold_vrc(ISN_UC)")
        finally:
            con_processed.close()

        total_validado = con_duck.execute("SELECT COUNT(*) FROM raw_iqs_vrc").fetchone()[0]
        caminho_resumo = MARTS_DIR / f"VRC_IQS_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO.TXT"
        caminho_amostra = MARTS_DIR / f"VRC_IQS_{ANOMES}_{TIMESTAMP_ARQ}_AMOSTRA.CSV"

        con_duck.execute(
            f"""
            COPY (
                SELECT *
                FROM raw_iqs_vrc
                LIMIT 100
            )
            TO '{caminho_amostra.as_posix()}'
            WITH (
                HEADER TRUE,
                DELIMITER '|'
            )
            """
        )

        with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
            arquivo.write("EXTRACAO VRC IQS\n")
            arquivo.write(f"ANOMES: {ANOMES}\n")
            arquivo.write(f"SQL: {SQL_PATH}\n")
            arquivo.write(f"DuckDB raw IQS: {IQS_RAW_DUCKDB_PATH}\n")
            arquivo.write("Tabela raw: raw_iqs_vrc\n")
            arquivo.write("Tabela processada compatibilidade: gold_vrc\n")
            arquivo.write(f"Registros extraidos: {total_validado}\n")
            arquivo.write(f"Soma VRC: {soma_vrc}\n")
            arquivo.write(f"Min VRC: {min_vrc}\n")
            arquivo.write(f"Max VRC: {max_vrc}\n")
            arquivo.write(f"Amostra CSV: {caminho_amostra}\n")

        print(f"Extracao VRC finalizada. Registros: {total_validado:,}")
        print(f"Amostra: {caminho_amostra}")
        print(f"Resumo: {caminho_resumo}")
    finally:
        con_duck.close()


if __name__ == "__main__":
    extrair_vrc()

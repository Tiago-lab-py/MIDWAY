import os
from datetime import datetime
from pathlib import Path

import duckdb
import oracledb
import pandas as pd
from dotenv import load_dotenv

from midway.transform.iqs_raw_utils import iqs_raw_path, materializar_gold_table, processed_path


load_dotenv(override=True)

GEO_UID = os.getenv("GEO_UID", "cons_gdg")
GEO_PWD = os.getenv("GEO_PWD", "")
GEO_DB = os.getenv("GEO_DB", "GEOPRD.world")
GEO_CONFIG_DIR = os.getenv("GEO_CONFIG_DIR", os.getenv("IQS_CONFIG_DIR"))
ANOMES = os.getenv("ANOMES", "202607")
REEXTRAIR_GEO = os.getenv("REEXTRAIR_GEO", "0") == "1"

BASE_DIR = Path("data")
MARTS_DIR = BASE_DIR / "marts"
RAW_DIR = BASE_DIR / "raw"
SQL_PATH = Path("SQL") / "GEO_chaves_ra.sql"
IQS_RAW_DUCKDB_PATH = iqs_raw_path(ANOMES)
PROCESSED_DUCKDB_PATH = processed_path(ANOMES)
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")


def conectar_oracle_geo():
    if GEO_CONFIG_DIR:
        os.environ["TNS_ADMIN"] = GEO_CONFIG_DIR
        oracledb.defaults.config_dir = GEO_CONFIG_DIR

    return oracledb.connect(
        user=GEO_UID,
        password=GEO_PWD,
        dsn=GEO_DB,
    )


def exportar_csv(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.astype("string").fillna("").to_csv(
        caminho,
        sep="|",
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )


def extrair_geo():
    if not SQL_PATH.exists():
        raise RuntimeError(f"SQL GEO nao encontrado: {SQL_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Extraindo dados GEO (Chaves RA)...")
    sql = SQL_PATH.read_text(encoding="utf-8")

    con_oracle = conectar_oracle_geo()
    try:
        df = pd.read_sql_query(sql, con_oracle)
    finally:
        con_oracle.close()

    df.columns = [col.upper() for col in df.columns]

    caminho_csv = MARTS_DIR / f"GEO_Chaves_RA_{ANOMES}_{TIMESTAMP_ARQ}.CSV"
    caminho_resumo = MARTS_DIR / f"GEO_Chaves_RA_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO.TXT"
    exportar_csv(df, caminho_csv)

    # Gravar no DuckDB RAW
    con_duck = duckdb.connect(str(IQS_RAW_DUCKDB_PATH))
    try:
        con_duck.register("geo_tmp", df)
        con_duck.execute("CREATE OR REPLACE TABLE raw_geo_chaves_ra AS SELECT * FROM geo_tmp")
        con_duck.unregister("geo_tmp")
    finally:
        con_duck.close()

    # Materializar no DuckDB Processed
    if PROCESSED_DUCKDB_PATH.exists():
        con_proc = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
        try:
            con_proc.register("geo_tmp", df)
            con_proc.execute("CREATE OR REPLACE TABLE gold_geo_chaves_ra AS SELECT * FROM geo_tmp")
            con_proc.unregister("geo_tmp")
        finally:
            con_proc.close()

    total = len(df)
    with open(caminho_resumo, "w", encoding="utf-8") as arquivo:
        arquivo.write("EXTRACAO GEO / CHAVES RA\n")
        arquivo.write(f"Data Extracao: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        arquivo.write(f"Instancia GEO: {GEO_DB}\n")
        arquivo.write(f"Total Registros Extraidos: {total:,}\n")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Extracao GEO finalizada com sucesso! Registros: {total:,}")
    return df


if __name__ == "__main__":
    extrair_geo()

import os
from datetime import datetime
from pathlib import Path

import duckdb
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202605")

DATA_DIR = Path("data")
RAW_DUCKDB_PATH = DATA_DIR / "raw" / f"iqs_adms_raw_{ANOMES}.duckdb"
MARTS_DIR = DATA_DIR / "marts"
MARTS_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")
CAMINHO_CSV = MARTS_DIR / f"Amostra_RAW_HIADMS_{ANOMES}_{TIMESTAMP_ARQ}.CSV"


def sql_literal(valor):
    return "'" + str(valor).replace("\\", "/").replace("'", "''") + "'"


if not RAW_DUCKDB_PATH.exists():
    raise FileNotFoundError(f"DuckDB bruto nao encontrado: {RAW_DUCKDB_PATH}")

con = duckdb.connect(str(RAW_DUCKDB_PATH), read_only=True)

try:
    total = con.execute("SELECT COUNT(*) FROM hiadms_raw").fetchone()[0]
    con.execute(f"""
        COPY (
            SELECT *
            FROM hiadms_raw
            LIMIT 100
        )
        TO {sql_literal(CAMINHO_CSV.as_posix())}
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
    """)
finally:
    con.close()

print(f"Amostra exportada: {CAMINHO_CSV}")
print(f"Total de registros no RAW: {total:,}")

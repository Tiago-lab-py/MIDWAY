import duckdb
from pathlib import Path

db_path = Path("data/processed/iqs_adms_processed_202607.duckdb")

with duckdb.connect(str(db_path), read_only=True) as con:
    tables = con.execute("SELECT table_name FROM information_schema.tables").fetchall()
    for t in tables:
        print(t[0])

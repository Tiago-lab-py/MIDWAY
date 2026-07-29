import duckdb
from pathlib import Path

db_path = Path("data/processed/iqs_adms_processed_202607.duckdb")

with duckdb.connect(str(db_path), read_only=True) as con:
    cols = con.execute("DESCRIBE gold_interrupcao_tratada").fetchall()
    for c in cols:
        name = c[0].upper()
        if 'CHV' in name or 'RA' in name or 'OPER' in name or 'TIPO' in name:
            print(name)

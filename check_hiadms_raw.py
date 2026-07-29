import duckdb
from pathlib import Path

raw_path = Path("data/raw/iqs_adms_raw_202607.duckdb")

with duckdb.connect(str(raw_path), read_only=True) as con:
    try:
        cols = con.execute("DESCRIBE hiadms_raw").fetchall()
        for col in cols:
            if "MANOBRA" in col[0] or "TRAT_DIF" in col[0]:
                print(col[0])
    except Exception as e:
        print(f"Erro: {e}")

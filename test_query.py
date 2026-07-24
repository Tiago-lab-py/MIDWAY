import duckdb

db_path = "data/processed/iqs_adms_processed_202607.duckdb"
raw_path = "data/raw/iqs_adms_raw_202607.duckdb"

try:
    with duckdb.connect(str(db_path), read_only=True) as con:
        con.execute(f"ATTACH '{raw_path}' AS raw_db (READ_ONLY)")
        print(con.execute("SELECT MAX(UC_FATURADA) FROM gold_consumidores WHERE REGIONAL_TOTAL = 'COPEL'").fetchall())
except Exception as e:
    print("Error:", e)

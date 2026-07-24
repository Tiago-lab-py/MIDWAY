import duckdb

db_path = "data/processed/iqs_adms_processed_202607.duckdb"
with duckdb.connect(str(db_path), read_only=True) as con:
    tables = con.execute("SHOW TABLES").fetchall()
    print("Tables in processed:")
    for t in tables:
        print(t[0])

raw_path = "data/raw/iqs_adms_raw_202607.duckdb"
with duckdb.connect(str(raw_path), read_only=True) as con:
    tables = con.execute("SHOW TABLES").fetchall()
    print("Tables in raw:")
    for t in tables:
        print(t[0])

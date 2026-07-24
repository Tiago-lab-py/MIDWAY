import duckdb

raw_path = "data/raw/iqs_raw_202607.duckdb"
with duckdb.connect(str(raw_path), read_only=True) as con:
    tables = con.execute("SHOW TABLES").fetchall()
    print("Tables in iqs_raw:")
    for t in tables:
        print(t[0])
        cols = con.execute(f"DESCRIBE {t[0]}").fetchall()
        print([c[0] for c in cols])

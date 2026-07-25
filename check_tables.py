import duckdb
from pathlib import Path

def run():
    anomes = "202607"
    db_path = Path("data/processed") / f"iqs_adms_processed_{anomes}.duckdb"
    
    with duckdb.connect(str(db_path), read_only=True) as con:
        tables = con.execute("SELECT table_name FROM duckdb_tables() WHERE schema_name = 'main'").fetchall()
        print("Tabelas encontradas:")
        for t in sorted([row[0] for row in tables]):
            print(f" - {t}")
            
if __name__ == "__main__":
    run()

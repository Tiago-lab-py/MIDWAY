import duckdb
import traceback

def test_db():
    db_path = "data/processed/iqs_adms_processed_202606.duckdb"
    raw_path = "data/raw/iqs_adms_raw_202606.duckdb"
    print(f"Testing {db_path} and {raw_path}")
    try:
        with duckdb.connect(db_path, read_only=True) as con:
            con.execute(f"ATTACH '{raw_path}' AS raw_db (READ_ONLY)")
            print("Attached raw_db.")
            tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()
            print("Tables in processed:", [t[0] for t in tables])
            
            try:
                con.execute("SELECT MAX(UC_FATURADA) FROM gold_consumidores")
                print("gold_consumidores is OK")
            except Exception as e:
                print("gold_consumidores FAILED:", str(e))
                
            try:
                con.execute("SELECT * FROM raw_db.hiadms_raw LIMIT 1")
                print("raw_db.hiadms_raw is OK")
            except Exception as e:
                print("raw_db.hiadms_raw FAILED:", str(e))

            try:
                con.execute("SELECT * FROM gold_uc_fatura LIMIT 1")
                print("gold_uc_fatura is OK")
            except Exception as e:
                print("gold_uc_fatura FAILED:", str(e))

            try:
                con.execute("SELECT * FROM gold_apuracao_previa LIMIT 1")
                print("gold_apuracao_previa is OK")
            except Exception as e:
                print("gold_apuracao_previa FAILED:", str(e))

    except Exception as e:
        print("ERROR:")
        traceback.print_exc()

if __name__ == "__main__":
    test_db()

import duckdb
from pathlib import Path
import threading

db_path = Path("data/processed/iqs_adms_processed_202607.duckdb")

def connect_db():
    try:
        print("Connecting...")
        con = duckdb.connect(str(db_path), read_only=True)
        print("Connected!")
        import time
        time.sleep(2)
        con.close()
        print("Closed.")
    except Exception as e:
        print(f"Error: {e}")

t1 = threading.Thread(target=connect_db)
t2 = threading.Thread(target=connect_db)

t1.start()
import time
time.sleep(0.5)
t2.start()

t1.join()
t2.join()

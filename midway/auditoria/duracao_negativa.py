import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

from midway.controle_execucao import configurar_logger

load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
BASE_DIR = Path("data")
PROCESSED_DUCKDB_PATH = BASE_DIR / "processed" / f"iqs_adms_processed_{ANOMES}.duckdb"
EXPORT_DIR = BASE_DIR / "export" / "duracao_negativa"
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")

def executar_auditoria_duracao_negativa():
    logger = configurar_logger("duracao_negativa", ANOMES)
    logger.info("Iniciando auditoria de duracao negativa (fim < inicio)...")

    if not PROCESSED_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
            ).fetchall()
        }

        if "adms_iqs_export" not in tables:
            raise RuntimeError("Tabela adms_iqs_export nao encontrada. Execute run.bat tratamento antes.")

        con.execute("""
            CREATE OR REPLACE TABLE Auditoria_Duracao_Negativa AS
            SELECT *
            FROM adms_iqs_export
            WHERE DATA_HORA_FIM_INTRP < DATA_HORA_INIC_INTRP
        """)
        
        df = con.execute("SELECT * FROM Auditoria_Duracao_Negativa").df()
        
        if df.empty:
            logger.info("Nenhuma interrupcao com duracao negativa encontrada.")
            return

        caminho_csv = EXPORT_DIR / f"Auditoria_Duracao_Negativa_{TIMESTAMP_ARQ}.csv"
        df.to_csv(caminho_csv, sep=";", index=False, encoding="utf-8-sig")
        logger.info(f"Auditoria concluida. {len(df)} registros encontrados e exportados para {caminho_csv}")

    finally:
        con.close()

if __name__ == "__main__":
    executar_auditoria_duracao_negativa()

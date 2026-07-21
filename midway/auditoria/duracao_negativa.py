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

        if "adms_iqs_alterados" not in tables:
            raise RuntimeError("Tabela adms_iqs_alterados nao encontrada. Execute run.bat tratamento antes.")
        
        con.execute(f"ATTACH '{Path('data/raw').resolve()}/hiadms_raw_{ANOMES}.duckdb' AS raw_db (READ_ONLY)")

        con.execute("""
            CREATE OR REPLACE TABLE Auditoria_Duracao_Negativa AS
            SELECT 
                CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
                CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS NUM_UC_UCI,
                CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                r.DATA_HORA_INIC_INTRP_ULT_HIADMS AS DATA_HORA_INIC_INTRP,
                r.DATA_HORA_FIM_INTRP_ULT_HIADMS AS DATA_HORA_FIM_INTRP
            FROM adms_iqs_alterados t
            JOIN raw_db.hiadms_raw r
              ON CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) = t.NUM_SEQ_INTRP
             AND CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) = t.NUM_UC_UCI
             AND CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) = t.NUM_OCORRENCIA_ADMS
            WHERE r.DATA_HORA_FIM_INTRP_ULT_HIADMS < r.DATA_HORA_INIC_INTRP_ULT_HIADMS
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

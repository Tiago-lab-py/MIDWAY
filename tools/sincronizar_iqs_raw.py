import os
import sys
from pathlib import Path

import duckdb
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from midway.transform.iqs_raw_utils import iqs_raw_path, materializar_gold_de_iqs_raw, processed_path


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")


def sincronizar_iqs_raw():
    raw_path = iqs_raw_path(ANOMES)
    processed = processed_path(ANOMES)

    if not raw_path.exists():
        raise RuntimeError(f"DuckDB raw IQS nao encontrado: {raw_path}")

    processed.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(processed))
    try:
        materializadas = materializar_gold_de_iqs_raw(con, ANOMES)
    finally:
        con.close()

    if not materializadas:
        raise RuntimeError(
            f"Nenhuma tabela raw_iqs_* encontrada em {raw_path}. "
            "Verifique se o arquivo IQS raw foi populado."
        )

    print(f"Origem IQS raw: {raw_path}")
    print(f"Destino processed: {processed}")
    print("Tabelas materializadas: " + ", ".join(materializadas))


if __name__ == "__main__":
    sincronizar_iqs_raw()

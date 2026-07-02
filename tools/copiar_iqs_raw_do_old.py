import os
import sys
from pathlib import Path

import duckdb
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from midway.transform.iqs_raw_utils import IQS_RAW_TABLES, iqs_raw_path, materializar_gold_de_iqs_raw, processed_path


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
PROCESSED_DIR = Path("data") / "processed"
OLD_DUCKDB_PATH = Path(
    os.getenv(
        "IQS_OLD_PROCESSED_PATH",
        str(PROCESSED_DIR / f"iqs_adms_processed_{ANOMES}_old.duckdb"),
    )
)


def tabela_existe(con, nome_tabela: str, schema: str = "main") -> bool:
    try:
        con.execute(f"SELECT COUNT(*) FROM {schema}.{nome_tabela}").fetchone()
    except duckdb.CatalogException:
        return False
    return True


def copiar_iqs_raw_do_old():
    if not OLD_DUCKDB_PATH.exists():
        raise RuntimeError(f"DuckDB antigo nao encontrado: {OLD_DUCKDB_PATH}")

    raw_path = iqs_raw_path(ANOMES)
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    con_raw = duckdb.connect(str(raw_path))
    try:
        con_raw.execute(f"ATTACH '{OLD_DUCKDB_PATH.as_posix()}' AS old_db (READ_ONLY)")

        for raw_table, gold_table in IQS_RAW_TABLES.items():
            if not tabela_existe(con_raw, gold_table, schema="old_db"):
                print(f"Ignorando {gold_table}: tabela ausente no old.")
                continue

            con_raw.execute(
                f"""
                CREATE OR REPLACE TABLE {raw_table} AS
                SELECT *
                FROM old_db.{gold_table}
                """
            )
            total = con_raw.execute(f"SELECT COUNT(*) FROM {raw_table}").fetchone()[0]
            print(f"{raw_table}: {total:,} registros copiados de {gold_table}.")
    finally:
        con_raw.close()

    con_processed = duckdb.connect(str(processed_path(ANOMES)))
    try:
        materializadas = materializar_gold_de_iqs_raw(con_processed, ANOMES)
    finally:
        con_processed.close()

    print(f"DuckDB raw IQS atualizado: {raw_path}")
    print("Tabelas gold atualizadas: " + ", ".join(materializadas))


if __name__ == "__main__":
    copiar_iqs_raw_do_old()

import os
from pathlib import Path

import duckdb


BASE_DIR = Path("data")
RAW_DIR = BASE_DIR / "raw"
PROCESSED_DIR = BASE_DIR / "processed"


IQS_RAW_TABLES = {
    "raw_iqs_consumidores": "gold_consumidores",
    "raw_iqs_uc_fatura": "gold_uc_fatura",
    "raw_iqs_vrc": "gold_vrc",
    "raw_iqs_metas_uc": "gold_metas_uc",
}

IQS_SILVER_TABLES = {
    "raw_iqs_consumidores": "silver_iqs_consumidores",
    "raw_iqs_uc_fatura": "silver_iqs_uc_fatura",
    "raw_iqs_vrc": "silver_iqs_vrc",
    "raw_iqs_metas_uc": "silver_iqs_metas_uc",
}


def iqs_raw_path(anomes: str) -> Path:
    caminho_env = os.getenv("IQS_RAW_DUCKDB_PATH")
    if caminho_env and caminho_env.strip():
        return Path(caminho_env)
    return RAW_DIR / f"iqs_raw_{anomes}.duckdb"


def processed_path(anomes: str) -> Path:
    return PROCESSED_DIR / f"iqs_adms_processed_{anomes}.duckdb"


def tabela_existe(con, nome_tabela: str, schema: str = "main") -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = ?
              AND table_name = ?
            """,
            [schema, nome_tabela],
        ).fetchone()[0]
        > 0
    )


def criar_ou_substituir_por_dataframe(con, nome_tabela: str, nome_view: str, df):
    con.register(nome_view, df)
    con.execute(f"CREATE OR REPLACE TABLE {nome_tabela} AS SELECT * FROM {nome_view}")
    con.unregister(nome_view)


def anexar_iqs_raw(con, anomes: str, read_only: bool = True) -> bool:
    caminho = iqs_raw_path(anomes)
    if not caminho.exists():
        return False

    modo = " (READ_ONLY)" if read_only else ""
    try:
        con.execute(f"ATTACH '{caminho.as_posix()}' AS iqs_raw{modo}")
    except duckdb.BinderException:
        pass
    return True


def materializar_gold_de_iqs_raw(con_processed, anomes: str) -> list[str]:
    if not anexar_iqs_raw(con_processed, anomes, read_only=True):
        return []

    materializadas = []
    for raw_table, gold_table in IQS_RAW_TABLES.items():
        silver_table = IQS_SILVER_TABLES[raw_table]
        try:
            con_processed.execute(f"SELECT COUNT(*) FROM iqs_raw.{raw_table}").fetchone()
        except duckdb.CatalogException:
            continue
        else:
            con_processed.execute(
                f"""
                CREATE OR REPLACE TABLE {silver_table} AS
                SELECT *
                FROM iqs_raw.{raw_table}
                """
            )
            con_processed.execute(
                f"""
                CREATE OR REPLACE TABLE {gold_table} AS
                SELECT *
                FROM {silver_table}
                """
            )
            materializadas.extend([silver_table, gold_table])

    return materializadas


def materializar_gold_table(anomes: str, raw_table: str, gold_table: str):
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    con_processed = duckdb.connect(str(processed_path(anomes)))
    try:
        anexar_iqs_raw(con_processed, anomes, read_only=True)
        silver_table = IQS_SILVER_TABLES.get(
            raw_table, raw_table.replace("raw_", "silver_", 1)
        )
        con_processed.execute(
            f"""
            CREATE OR REPLACE TABLE {silver_table} AS
            SELECT *
            FROM iqs_raw.{raw_table}
            """
        )
        con_processed.execute(
            f"""
            CREATE OR REPLACE TABLE {gold_table} AS
            SELECT *
            FROM {silver_table}
            """
        )
    finally:
        con_processed.close()

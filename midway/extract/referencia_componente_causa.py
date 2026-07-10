import os
from datetime import datetime
from pathlib import Path

import duckdb
import oracledb
import pandas as pd
from dotenv import load_dotenv

from midway.transform.iqs_raw_utils import iqs_raw_path, materializar_gold_table, processed_path


load_dotenv()

IQS_UID = os.getenv("IQS_UID")
IQS_PWD = os.getenv("IQS_PWD")
IQS_DB = os.getenv("IQS_DB")
IQS_CONFIG_DIR = os.getenv("IQS_CONFIG_DIR")
ANOMES = os.getenv("ANOMES", "202606")
REEXTRAIR_REFERENCIA_IQS = os.getenv("REEXTRAIR_REFERENCIA_IQS", "0") == "1"

BASE_DIR = Path("data")
MARTS_DIR = BASE_DIR / "marts"
RAW_DIR = BASE_DIR / "raw"
SQL_PATH = Path("SQL") / "IQS_referencia_componente_causa.sql"
IQS_RAW_DUCKDB_PATH = iqs_raw_path(ANOMES)
PROCESSED_DUCKDB_PATH = processed_path(ANOMES)
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")
RAW_TABLE = "raw_iqs_referencia_componente_causa"
GOLD_TABLE = "gold_iqs_referencia_componente_causa"


def conectar_oracle():
    if IQS_CONFIG_DIR:
        os.environ["TNS_ADMIN"] = IQS_CONFIG_DIR
        oracledb.defaults.config_dir = IQS_CONFIG_DIR

    return oracledb.connect(
        user=IQS_UID,
        password=IQS_PWD,
        dsn=IQS_DB,
    )


def tabela_existe(con, nome_tabela: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [nome_tabela],
        ).fetchone()[0]
        > 0
    )


def normalizar_codigo(valor, preencher_zero: bool = False) -> str:
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().upper()
    if not texto:
        return ""
    if texto.endswith(".0") and texto[:-2].isdigit():
        texto = texto[:-2]
    if preencher_zero and texto.isdigit() and len(texto) == 1:
        return f"0{texto}"
    return texto


def normalizar_referencia(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [col.upper() for col in df.columns]

    for coluna in ["DESC_GRUPO_GCR", "DESC_COMP", "DESC_CAUSA"]:
        if coluna in df.columns:
            df[coluna] = df[coluna].fillna("").astype(str).str.strip().str.upper()

    df["COD_GRUPO_GCR"] = df.get("COD_GRUPO_GCR", "").map(normalizar_codigo)
    df["COD_COMP"] = df.get("COD_COMP", "").map(normalizar_codigo)
    df["COD_CAUSA"] = df.get("COD_CAUSA", "").map(lambda value: normalizar_codigo(value, preencher_zero=True))

    df = df[(df["COD_COMP"] != "") & (df["COD_CAUSA"] != "")].copy()
    df["GRUPO_COMPONENTE_REDE"] = df["COD_GRUPO_GCR"] + " - " + df["DESC_GRUPO_GCR"]
    df["COMPONENTE_REDE"] = df["COD_COMP"] + " - " + df["DESC_COMP"]
    df["CAUSA_REDE"] = df["COD_CAUSA"] + " - " + df["DESC_CAUSA"]
    df["CHAVE_COMP_CAUSA"] = df["COD_COMP"] + "/" + df["COD_CAUSA"]

    colunas_ordem = ["COD_GRUPO_GCR", "DESC_GRUPO_GCR", "COD_COMP", "DESC_COMP", "COD_CAUSA", "DESC_CAUSA"]
    df = df.drop_duplicates(subset=["COD_GRUPO_GCR", "COD_COMP", "COD_CAUSA"])
    return df.sort_values(colunas_ordem).reset_index(drop=True)


def exportar_amostra(con, caminho_amostra: Path):
    con.execute(
        f"""
        COPY (
            SELECT *
            FROM {RAW_TABLE}
            ORDER BY COD_GRUPO_GCR, DESC_GRUPO_GCR, COD_COMP, DESC_COMP, COD_CAUSA, DESC_CAUSA
            LIMIT 500
        )
        TO '{caminho_amostra.as_posix()}'
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )


def criar_indices(con):
    colunas = [row[1] for row in con.execute(f"PRAGMA table_info('{RAW_TABLE}')").fetchall()]
    if "COD_GRUPO_GCR" in colunas:
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{RAW_TABLE}_grupo ON {RAW_TABLE}(COD_GRUPO_GCR)")
    if "COD_COMP" in colunas:
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{RAW_TABLE}_comp ON {RAW_TABLE}(COD_COMP)")
    if "COD_CAUSA" in colunas:
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{RAW_TABLE}_causa ON {RAW_TABLE}(COD_CAUSA)")
    if "CHAVE_COMP_CAUSA" in colunas:
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{RAW_TABLE}_chave ON {RAW_TABLE}(CHAVE_COMP_CAUSA)")


def materializar_referencia():
    materializar_gold_table(ANOMES, RAW_TABLE, GOLD_TABLE)

    con_processed = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    try:
        con_processed.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{GOLD_TABLE}_grupo ON {GOLD_TABLE}(COD_GRUPO_GCR)"
        )
        con_processed.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{GOLD_TABLE}_comp ON {GOLD_TABLE}(COD_COMP)"
        )
        con_processed.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{GOLD_TABLE}_causa ON {GOLD_TABLE}(COD_CAUSA)"
        )
        con_processed.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{GOLD_TABLE}_chave ON {GOLD_TABLE}(CHAVE_COMP_CAUSA)"
        )
    finally:
        con_processed.close()

    print(f"Tabela {GOLD_TABLE} atualizada no processado.")


def extrair_referencia_componente_causa(chunksize: int = 100_000):
    if not SQL_PATH.exists():
        raise RuntimeError(f"SQL nao encontrado: {SQL_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    precisa_materializar = False
    con_duck = duckdb.connect(str(IQS_RAW_DUCKDB_PATH))

    try:
        if tabela_existe(con_duck, RAW_TABLE) and not REEXTRAIR_REFERENCIA_IQS:
            total_existente = con_duck.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
            print(f"Tabela {RAW_TABLE} ja existe.")
            print(f"Registros existentes: {total_existente:,}")
            print("Defina REEXTRAIR_REFERENCIA_IQS=1 para extrair novamente.")
            precisa_materializar = True
        else:
            print(f"Extraindo referencia componente/causa IQS ANOMES={ANOMES}...")
            print(f"SQL: {SQL_PATH}")
            print(f"DuckDB raw IQS destino: {IQS_RAW_DUCKDB_PATH}")

            sql = SQL_PATH.read_text(encoding="utf-8").strip()
            if sql.endswith(";"):
                sql = sql[:-1].strip()

            con_oracle = conectar_oracle()
            primeiro_lote = True
            total = 0

            try:
                con_duck.execute(f"DROP TABLE IF EXISTS {RAW_TABLE}")

                for df in pd.read_sql_query(sql, con_oracle, chunksize=chunksize):
                    if df.empty:
                        continue

                    df = normalizar_referencia(df)
                    if df.empty:
                        continue

                    con_duck.register("referencia_iqs_lote_tmp", df)

                    if primeiro_lote:
                        con_duck.execute(
                            f"CREATE TABLE {RAW_TABLE} AS SELECT * FROM referencia_iqs_lote_tmp"
                        )
                        primeiro_lote = False
                    else:
                        con_duck.execute(f"INSERT INTO {RAW_TABLE} SELECT * FROM referencia_iqs_lote_tmp")

                    con_duck.unregister("referencia_iqs_lote_tmp")
                    total += len(df)
                    print(f"Referencias IQS extraidas: {total:,}")
            finally:
                con_oracle.close()

            if primeiro_lote:
                raise RuntimeError("Nenhum registro de referencia componente/causa IQS extraido.")

            con_duck.execute(f"CREATE OR REPLACE TABLE {RAW_TABLE} AS SELECT DISTINCT * FROM {RAW_TABLE}")
            criar_indices(con_duck)
            total_validado = con_duck.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
            caminho_resumo = MARTS_DIR / f"Referencia_Componente_Causa_IQS_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO.TXT"
            caminho_amostra = MARTS_DIR / f"Referencia_Componente_Causa_IQS_{ANOMES}_{TIMESTAMP_ARQ}_AMOSTRA.CSV"

            exportar_amostra(con_duck, caminho_amostra)

            with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
                arquivo.write("EXTRACAO REFERENCIA COMPONENTE/CAUSA IQS\n")
                arquivo.write(f"ANOMES: {ANOMES}\n")
                arquivo.write(f"SQL: {SQL_PATH}\n")
                arquivo.write(f"DuckDB raw IQS: {IQS_RAW_DUCKDB_PATH}\n")
                arquivo.write(f"Tabela raw: {RAW_TABLE}\n")
                arquivo.write("Tabela silver: silver_iqs_referencia_componente_causa\n")
                arquivo.write(f"Tabela gold: {GOLD_TABLE}\n")
                arquivo.write(f"Registros extraidos: {total_validado}\n")
                arquivo.write(f"Amostra CSV: {caminho_amostra}\n")

            print(f"Extracao referencia IQS finalizada. Registros: {total_validado:,}")
            print(f"Amostra: {caminho_amostra}")
            print(f"Resumo: {caminho_resumo}")
            precisa_materializar = True
    finally:
        con_duck.close()

    if precisa_materializar:
        materializar_referencia()


if __name__ == "__main__":
    extrair_referencia_componente_causa()

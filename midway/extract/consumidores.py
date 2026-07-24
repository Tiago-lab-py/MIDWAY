import os
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import oracledb
from dotenv import load_dotenv

from midway.transform.iqs_raw_utils import (
    criar_ou_substituir_por_dataframe,
    iqs_raw_path,
    materializar_gold_table,
)


load_dotenv(override=True)

IQS_UID = os.getenv("IQS_UID")
IQS_PWD = os.getenv("IQS_PWD")
IQS_DB = os.getenv("IQS_DB")
IQS_CONFIG_DIR = os.getenv("IQS_CONFIG_DIR")
ANOMES = os.getenv("ANOMES", "202606")

BASE_DIR = Path("data")
MARTS_DIR = BASE_DIR / "marts"
RAW_DIR = BASE_DIR / "raw"
SQL_PATH = Path("SQL") / "IQS_consumidor.sql"
IQS_RAW_DUCKDB_PATH = iqs_raw_path(ANOMES)
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")


def anomes_oracle() -> str:
    return f"{ANOMES[:4]}-{ANOMES[4:6]}"


def conectar_oracle():
    if IQS_CONFIG_DIR:
        os.environ["TNS_ADMIN"] = IQS_CONFIG_DIR
        oracledb.defaults.config_dir = IQS_CONFIG_DIR

    return oracledb.connect(
        user=IQS_UID,
        password=IQS_PWD,
        dsn=IQS_DB,
    )


def exportar_csv(df: pd.DataFrame, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df.astype("string").fillna("").to_csv(
        caminho,
        sep="|",
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )


def extrair_consumidores():
    if not SQL_PATH.exists():
        raise RuntimeError(f"SQL nao encontrado: {SQL_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Extraindo consumidores ANOMES={ANOMES} ({anomes_oracle()})...")
    sql = SQL_PATH.read_text(encoding="utf-8")

    con_oracle = conectar_oracle()
    try:
        df = pd.read_sql_query(
            sql,
            con_oracle,
            params={"anomes": anomes_oracle()},
        )
    finally:
        con_oracle.close()

    df.columns = [col.upper() for col in df.columns]

    caminho_csv = MARTS_DIR / f"Consumidores_IQS_{ANOMES}_{TIMESTAMP_ARQ}.CSV"
    caminho_resumo = MARTS_DIR / f"Consumidores_IQS_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO.TXT"
    exportar_csv(df, caminho_csv)

    total_copel = 0
    if not df.empty and {"REGIONAL_TOTAL", "UC_FATURADA"}.issubset(df.columns):
        filtro_copel = df["REGIONAL_TOTAL"].astype(str).str.upper().eq("COPEL")
        if filtro_copel.any():
            total_copel = df.loc[filtro_copel, "UC_FATURADA"].iloc[0]

    con_duck = duckdb.connect(str(IQS_RAW_DUCKDB_PATH))
    try:
        criar_ou_substituir_por_dataframe(
            con_duck,
            "raw_iqs_consumidores",
            "consumidores_tmp",
            df,
        )
    finally:
        con_duck.close()

    materializar_gold_table(ANOMES, "raw_iqs_consumidores", "gold_consumidores")

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("CONSUMIDORES IQS\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write(f"SQL: {SQL_PATH}\n")
        arquivo.write(f"Linhas extraidas: {len(df)}\n")
        arquivo.write(f"UC faturada COPEL: {total_copel}\n")
        arquivo.write(f"CSV conferencia: {caminho_csv}\n")
        arquivo.write(f"DuckDB raw IQS: {IQS_RAW_DUCKDB_PATH}\n")
        arquivo.write("Tabela raw: raw_iqs_consumidores\n")
        arquivo.write("Tabela processada compatibilidade: gold_consumidores\n")

    print(f"Consumidores extraidos: {len(df)}")
    print(f"UC faturada COPEL: {total_copel}")
    print(f"CSV conferencia: {caminho_csv}")
    print(f"Resumo: {caminho_resumo}")
    print(f"Tabela raw_iqs_consumidores materializada em {IQS_RAW_DUCKDB_PATH}.")
    print("Tabela gold_consumidores atualizada no processado.")


if __name__ == "__main__":
    extrair_consumidores()

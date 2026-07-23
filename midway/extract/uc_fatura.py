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
SQL_PATH = Path("SQL") / "IQS_uc_fatura.sql"
IQS_RAW_DUCKDB_PATH = iqs_raw_path(ANOMES)
TIMESTAMP_ARQ = datetime.now().strftime("%Y%m%d%H%M%S")


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


def extrair_uc_fatura():
    if not SQL_PATH.exists():
        raise RuntimeError(f"SQL nao encontrado: {SQL_PATH}")

    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Extraindo UCs de faturamento/apuracao ANOMES={ANOMES}...")
    sql = SQL_PATH.read_text(encoding="utf-8")

    con_oracle = conectar_oracle()
    try:
        df = pd.read_sql_query(sql, con_oracle, params={"anomes": ANOMES})
    finally:
        con_oracle.close()

    df.columns = [col.upper() for col in df.columns]
    df = df.drop_duplicates()

    caminho_csv = MARTS_DIR / f"UC_Fatura_IQS_{ANOMES}_{TIMESTAMP_ARQ}.CSV"
    caminho_resumo = MARTS_DIR / f"UC_Fatura_IQS_{ANOMES}_{TIMESTAMP_ARQ}_RESUMO.TXT"
    exportar_csv(df, caminho_csv)

    total_faturado = 0
    if "FATURADO" in df.columns:
        total_faturado = int(df["FATURADO"].astype(str).str.upper().eq("S").sum())

    con_duck = duckdb.connect(str(IQS_RAW_DUCKDB_PATH))
    try:
        criar_ou_substituir_por_dataframe(
            con_duck,
            "raw_iqs_uc_fatura",
            "uc_fatura_tmp",
            df,
        )
    finally:
        con_duck.close()

    materializar_gold_table(ANOMES, "raw_iqs_uc_fatura", "gold_uc_fatura")

    with caminho_resumo.open("w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write("UC FATURA IQS\n")
        arquivo.write(f"ANOMES: {ANOMES}\n")
        arquivo.write(f"SQL: {SQL_PATH}\n")
        arquivo.write(f"UCs distintas extraidas: {len(df)}\n")
        arquivo.write(f"UCs com FATURADO='S': {total_faturado}\n")
        arquivo.write(f"CSV conferencia: {caminho_csv}\n")
        arquivo.write(f"DuckDB raw IQS: {IQS_RAW_DUCKDB_PATH}\n")
        arquivo.write("Tabela raw: raw_iqs_uc_fatura\n")
        arquivo.write("Tabela processada compatibilidade: gold_uc_fatura\n")

    print(f"UCs distintas extraidas: {len(df):,}")
    print(f"UCs com FATURADO='S': {total_faturado:,}")
    print(f"CSV conferencia: {caminho_csv}")
    print(f"Resumo: {caminho_resumo}")
    print(f"Tabela raw_iqs_uc_fatura materializada em {IQS_RAW_DUCKDB_PATH}.")
    print("Tabela gold_uc_fatura atualizada no processado.")
    print()
    print("Extracao de UC fatura finalizada com sucesso.")


if __name__ == "__main__":
    extrair_uc_fatura()

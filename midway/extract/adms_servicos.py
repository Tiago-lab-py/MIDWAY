from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv


load_dotenv()

ANOMES = os.getenv("ANOMES", "202606")
REEXTRAIR_ADMS_SERVICOS = os.getenv("REEXTRAIR_ADMS_SERVICOS", "0") == "1"
ADMS_SERVICOS_BACKUP_DIR = Path(
    os.getenv("ADMS_SERVICOS_BACKUP_DIR", r"P:\Common\IQS\ADMS\Backup")
)
ADMS_SERVICOS_PATTERN = os.getenv("ADMS_SERVICOS_PATTERN", "IQS_SERVICOS_*.CSV")
ADMS_SERVICOS_MARGEM_DIAS = int(os.getenv("ADMS_SERVICOS_MARGEM_DIAS", "2"))
ADMS_SERVICOS_MARGEM_ARQUIVOS_DIAS = int(
    os.getenv("ADMS_SERVICOS_MARGEM_ARQUIVOS_DIAS", "10")
)

BASE_DIR = Path("data")
RAW_DIR = BASE_DIR / "raw"
MARTS_DIR = BASE_DIR / "marts"
TEMP_DIR = BASE_DIR / "temp"
RAW_DUCKDB_PATH = RAW_DIR / f"adms_servicos_raw_{ANOMES}.duckdb"
RAW_DUCKDB_INCOMPLETE_PATH = RAW_DIR / f"adms_servicos_raw_{ANOMES}.duckdb.incomplete"
RAW_TABLE = "raw_adms_servicos"
TIMESTAMP = datetime.now().strftime("%Y%m%d%H%M%S")

DATE_COLUMNS = [
    "DTHR_ALT_ACES",
    "DTHR_SOLIC_SRV",
    "DTHR_GERA_SRV",
    "DTHR_PREV_EXEC_SRV",
    "DTHR_PROG_EXEC_SRV",
    "DTHR_DESPACH_SRV",
    "DTHR_ULT_ALT_SRV",
    "DTHR_FECH_SRV",
    "DTHR_SAIDA_SRV",
    "DTHR_INIC_SRV",
    "DTHR_TERM_SRV",
    "DTHR_RETOR_SRV",
    "DTHR_AGUARD_EQUIPE_SRV",
    "DTHR_REENVIO_SRV",
]

REFERENCE_DATE_PRIORITY = [
    "DTHR_INIC_SRV",
    "DTHR_SOLIC_SRV",
    "DTHR_GERA_SRV",
    "DTHR_DESPACH_SRV",
    "DTHR_FECH_SRV",
]


def month_window() -> tuple[pd.Timestamp, pd.Timestamp]:
    inicio = pd.Timestamp(f"{ANOMES[:4]}-{ANOMES[4:6]}-01")
    fim = inicio + pd.offsets.MonthBegin(1)
    return inicio, fim


def extraction_window() -> tuple[pd.Timestamp, pd.Timestamp]:
    inicio, fim = month_window()
    margem = pd.Timedelta(days=ADMS_SERVICOS_MARGEM_DIAS)
    return inicio - margem, fim + margem


def file_window() -> tuple[pd.Timestamp, pd.Timestamp]:
    inicio, fim = month_window()
    return (
        inicio - pd.Timedelta(days=ADMS_SERVICOS_MARGEM_DIAS),
        fim + pd.Timedelta(days=ADMS_SERVICOS_MARGEM_ARQUIVOS_DIAS),
    )


def sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'main'
              AND table_name = ?
            """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


def timestamp_from_filename(path: Path) -> pd.Timestamp | None:
    match = re.search(r"IQS_SERVICOS_(\d{14})", path.name, flags=re.IGNORECASE)
    if not match:
        return None

    return pd.to_datetime(match.group(1), format="%Y%m%d%H%M%S", errors="coerce")


def listar_arquivos() -> list[Path]:
    if not ADMS_SERVICOS_BACKUP_DIR.exists():
        raise FileNotFoundError(
            "Pasta de servicos ADMS nao encontrada: "
            f"{ADMS_SERVICOS_BACKUP_DIR}. Configure ADMS_SERVICOS_BACKUP_DIR no .env."
        )

    patterns = {ADMS_SERVICOS_PATTERN, ADMS_SERVICOS_PATTERN.lower()}
    arquivos: list[Path] = []
    for pattern in patterns:
        arquivos.extend(ADMS_SERVICOS_BACKUP_DIR.glob(pattern))

    inicio_arquivo, fim_arquivo = file_window()
    filtrados = []
    for arquivo in sorted(set(arquivos)):
        data_arquivo = timestamp_from_filename(arquivo)
        if data_arquivo is not None and not pd.isna(data_arquivo):
            if data_arquivo < inicio_arquivo or data_arquivo >= fim_arquivo:
                continue
        filtrados.append(arquivo)

    if not filtrados:
        raise RuntimeError(
            f"Nenhum arquivo {ADMS_SERVICOS_PATTERN} encontrado em "
            f"{ADMS_SERVICOS_BACKUP_DIR} para ANOMES={ANOMES}."
        )

    return filtrados


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
        try:
            return pd.read_csv(
                path,
                sep="|",
                dtype=str,
                encoding=encoding,
                engine="python",
                keep_default_na=False,
                on_bad_lines="warn",
            )
        except UnicodeDecodeError as error:
            last_error = error

    if last_error:
        raise last_error
    raise RuntimeError(f"Nao foi possivel ler o arquivo: {path}")


def normalizar_dataframe(df: pd.DataFrame, arquivo: Path) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().upper() for col in df.columns]

    for column in df.columns:
        df[column] = df[column].astype(str).str.strip()

    for column in DATE_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce")

    reference = None
    for column in REFERENCE_DATE_PRIORITY:
        if column not in df.columns:
            continue
        reference = df[column] if reference is None else reference.fillna(df[column])

    if reference is None:
        raise RuntimeError(
            f"Arquivo {arquivo.name} nao possui coluna de data de servico conhecida."
        )

    df["DATA_REFERENCIA_SERVICO"] = reference
    inicio, fim = extraction_window()
    df = df[
        (df["DATA_REFERENCIA_SERVICO"] >= inicio)
        & (df["DATA_REFERENCIA_SERVICO"] < fim)
    ].copy()

    df["ANOMES_REFERENCIA"] = ANOMES
    df["ARQUIVO_ORIGEM"] = arquivo.name
    df["DTHR_CARGA_RAW"] = pd.Timestamp.now()
    return df


def criar_indices(con: duckdb.DuckDBPyConnection) -> None:
    columns = {
        row[1].upper()
        for row in con.execute(f"PRAGMA table_info('{RAW_TABLE}')").fetchall()
    }
    for column in ["PID_INTRP_SRVE", "NUM_SEQ_SERV", "COD_CAUSA_SRVE", "COD_COMP_SRVE"]:
        if column in columns:
            con.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{RAW_TABLE}_{column.lower()} "
                f"ON {RAW_TABLE}({column})"
            )


def exportar_amostra_e_resumo(
    con: duckdb.DuckDBPyConnection,
    total: int,
    arquivos_lidos: int,
) -> None:
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    amostra_path = MARTS_DIR / f"ADMS_Servicos_{ANOMES}_{TIMESTAMP}_AMOSTRA.CSV"
    resumo_path = MARTS_DIR / f"ADMS_Servicos_{ANOMES}_{TIMESTAMP}_RESUMO.TXT"

    con.execute(
        f"""
        COPY (
            SELECT *
            FROM {RAW_TABLE}
            LIMIT 100
        )
        TO {sql_literal(amostra_path)}
        WITH (
            HEADER TRUE,
            DELIMITER '|'
        )
        """
    )

    resumo = con.execute(
        f"""
        SELECT
            COUNT(*) AS LINHAS,
            COUNT(DISTINCT NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '')) AS INTERRUPCOES,
            COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), '')) AS SERVICOS,
            MIN(DATA_REFERENCIA_SERVICO) AS MENOR_DATA_REFERENCIA,
            MAX(DATA_REFERENCIA_SERVICO) AS MAIOR_DATA_REFERENCIA
        FROM {RAW_TABLE}
        """
    ).fetchone()

    inicio, fim = extraction_window()
    with resumo_path.open("w", encoding="utf-8", newline="\n") as file:
        file.write("EXTRACAO ADMS / SERVICOS\n")
        file.write(f"ANOMES: {ANOMES}\n")
        file.write(f"Fonte: {ADMS_SERVICOS_BACKUP_DIR}\n")
        file.write(f"Padrao: {ADMS_SERVICOS_PATTERN}\n")
        file.write(f"Janela: {inicio} <= DATA_REFERENCIA_SERVICO < {fim}\n")
        file.write(f"DuckDB raw: {RAW_DUCKDB_PATH}\n")
        file.write(f"Tabela raw: {RAW_TABLE}\n")
        file.write(f"Arquivos lidos: {arquivos_lidos}\n")
        file.write(f"Registros extraidos: {total}\n")
        file.write(f"Registros validados: {resumo[0]}\n")
        file.write(f"Interrupcoes distintas: {resumo[1]}\n")
        file.write(f"Servicos distintos: {resumo[2]}\n")
        file.write(f"Menor data referencia: {resumo[3]}\n")
        file.write(f"Maior data referencia: {resumo[4]}\n")
        file.write(f"Amostra CSV: {amostra_path}\n")

    print(f"Amostra: {amostra_path}")
    print(f"Resumo: {resumo_path}")


def extrair_adms_servicos() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    MARTS_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    if RAW_DUCKDB_PATH.exists() and not REEXTRAIR_ADMS_SERVICOS:
        con = duckdb.connect(str(RAW_DUCKDB_PATH), read_only=True)
        try:
            if table_exists(con, RAW_TABLE):
                total = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
                print(f"Tabela {RAW_TABLE} ja existe em {RAW_DUCKDB_PATH}.")
                print(f"Registros existentes: {total:,}")
                print("Defina REEXTRAIR_ADMS_SERVICOS=1 para extrair novamente.")
                return
        finally:
            con.close()

    if RAW_DUCKDB_INCOMPLETE_PATH.exists():
        RAW_DUCKDB_INCOMPLETE_PATH.unlink()
    if REEXTRAIR_ADMS_SERVICOS and RAW_DUCKDB_PATH.exists():
        RAW_DUCKDB_PATH.unlink()

    arquivos = listar_arquivos()
    print(f"Extraindo servicos ADMS ANOMES={ANOMES}...")
    print(f"Fonte: {ADMS_SERVICOS_BACKUP_DIR}")
    print(f"Arquivos candidatos: {len(arquivos)}")
    print(f"DuckDB destino: {RAW_DUCKDB_PATH}")

    con = duckdb.connect(str(RAW_DUCKDB_INCOMPLETE_PATH))
    con.execute(f"SET temp_directory = {sql_literal(TEMP_DIR.as_posix())}")
    con.execute(f"DROP TABLE IF EXISTS {RAW_TABLE}")

    primeiro_lote = True
    total = 0
    arquivos_lidos = 0

    try:
        for arquivo in arquivos:
            print(f"Lendo: {arquivo.name}")
            df = read_csv_with_fallback(arquivo)
            df = normalizar_dataframe(df, arquivo)
            arquivos_lidos += 1

            if df.empty:
                continue

            con.register("adms_servicos_lote_tmp", df)
            if primeiro_lote:
                con.execute(
                    f"CREATE TABLE {RAW_TABLE} AS SELECT * FROM adms_servicos_lote_tmp"
                )
                primeiro_lote = False
            else:
                con.execute(f"INSERT INTO {RAW_TABLE} SELECT * FROM adms_servicos_lote_tmp")
            con.unregister("adms_servicos_lote_tmp")

            total += len(df)
            print(f"Servicos extraidos: {total:,}")

        if primeiro_lote:
            raise RuntimeError("Nenhum registro de servico ADMS extraido.")

        criar_indices(con)
        total_validado = con.execute(f"SELECT COUNT(*) FROM {RAW_TABLE}").fetchone()[0]
        if total_validado <= 0:
            raise RuntimeError("DuckDB bruto de servicos foi gerado sem registros.")

        exportar_amostra_e_resumo(con, total_validado, arquivos_lidos)
    finally:
        con.close()

    RAW_DUCKDB_INCOMPLETE_PATH.rename(RAW_DUCKDB_PATH)
    print(f"Extracao ADMS servicos finalizada. Registros: {total:,}")


if __name__ == "__main__":
    extrair_adms_servicos()

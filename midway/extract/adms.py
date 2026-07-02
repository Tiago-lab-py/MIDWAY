import os
from pathlib import Path

import duckdb
import oracledb
import pandas as pd
import polars as pl
from dotenv import load_dotenv

from midway.controle_execucao import (
    agora_iso,
    carregar_done,
    configurar_logger,
    gravar_done,
    lock_execucao,
    valor_verdadeiro,
)


# ============================================================
# .ENV
# ============================================================

load_dotenv()

IQS_UID = os.getenv("IQS_UID")
IQS_PWD = os.getenv("IQS_PWD")
IQS_DB = os.getenv("IQS_DB")
IQS_CONFIG_DIR = os.getenv("IQS_CONFIG_DIR")
ORACLE_CLIENT_LIB_DIR = os.getenv("ORACLE_CLIENT_LIB_DIR")
IQS_ORACLE_CLIENT_LIB_DIR = os.getenv("IQS_ORACLE_CLIENT_LIB_DIR")
IQS_ORACLE_THICK_MODE = valor_verdadeiro("IQS_ORACLE_THICK_MODE")
ANOMES = os.getenv("ANOMES", "202605")
REEXTRAIR = valor_verdadeiro("REEXTRAIR")
REGISTRAR_RAW = valor_verdadeiro("REGISTRAR_RAW")

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
TEMP_DIR = DATA_DIR / "temp"
RAW_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

RAW_DUCKDB_PATH = RAW_DIR / f"iqs_adms_raw_{ANOMES}.duckdb"
RAW_DUCKDB_INCOMPLETE_PATH = RAW_DIR / f"iqs_adms_raw_{ANOMES}.duckdb.incomplete"


def sql_literal(valor):
    return "'" + str(valor).replace("\\", "/").replace("'", "''") + "'"


# ============================================================
# ORACLE
# ============================================================

def conectar_oracle():
    connect_kwargs = {
        "user": IQS_UID,
        "password": IQS_PWD,
        "dsn": IQS_DB,
    }

    if IQS_CONFIG_DIR:
        connect_kwargs["config_dir"] = IQS_CONFIG_DIR

    if IQS_ORACLE_THICK_MODE or IQS_ORACLE_CLIENT_LIB_DIR:
        init_kwargs = {}

        if IQS_ORACLE_CLIENT_LIB_DIR:
            init_kwargs["lib_dir"] = IQS_ORACLE_CLIENT_LIB_DIR

        if IQS_CONFIG_DIR:
            init_kwargs["config_dir"] = IQS_CONFIG_DIR
            connect_kwargs.pop("config_dir", None)

        oracledb.init_oracle_client(**init_kwargs)

    return oracledb.connect(**connect_kwargs)


# ============================================================
# EXTRACAO IQS
# Ultimo registro por:
#   ocorrencia + interrupcao + UC
# ============================================================

SQL_EXTRACAO = """
SELECT *
FROM (
    SELECT
        h.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                h.PID_OCOR_INTRP_ULT_HIADMS,
                h.NUM_SEQ_INTRP_CHVP_HIADMS,
                h.NUM_UC_UCI_CHVP_HIADMS
            ORDER BY
                h.DTHR_INC_REGIS_HIADMS DESC NULLS LAST,
                h.NOME_ARQ_ADMS_HIADMS DESC NULLS LAST
        ) AS RN_ULT_REGISTRO
    FROM IQS.HIST_INTEGRACAO_ADMS h
    WHERE h.DATA_HORA_INIC_INTRP_ULT_HIADMS >= TO_DATE(:anomes || '01', 'YYYYMMDD')
      AND h.DATA_HORA_INIC_INTRP_ULT_HIADMS <  ADD_MONTHS(TO_DATE(:anomes || '01', 'YYYYMMDD'), 1)
      AND h.DATA_HORA_FIM_INTRP_ULT_HIADMS  >= TO_DATE(:anomes || '01', 'YYYYMMDD')
      AND h.DATA_HORA_FIM_INTRP_ULT_HIADMS  <  ADD_MONTHS(TO_DATE(:anomes || '01', 'YYYYMMDD'), 1)
      AND TRIM(h.ESTADO_INTRP_ULT_HIADMS) = '4'
)
WHERE RN_ULT_REGISTRO = 1
"""


def extrair_iqs_para_duckdb(chunksize: int = 100_000, logger=None):
    logger = logger or configurar_logger("extract", ANOMES)
    done = carregar_done("extract", ANOMES)

    if done and not REEXTRAIR:
        duckdb_path_done = Path(done.get("duckdb_path", ""))

        if not duckdb_path_done.exists():
            raise FileNotFoundError(
                f"Controle de extracao existe, mas o DuckDB bruto nao foi encontrado: "
                f"{duckdb_path_done}. Defina REEXTRAIR=1 para recriar."
            )

        logger.info("Extracao ja finalizada em %s", done.get("finished_at"))
        logger.info("DuckDB bruto registrado: %s", done.get("duckdb_path"))
        logger.info("Defina REEXTRAIR=1 para extrair novamente do Oracle.")
        return

    if RAW_DUCKDB_PATH.exists() and not REEXTRAIR:
        raise RuntimeError(
            f"DuckDB bruto existe sem controle finalizado: {RAW_DUCKDB_PATH}. "
            "Valide o arquivo e crie o controle ou defina REEXTRAIR=1."
        )

    with lock_execucao("extract", ANOMES) as started_at:
        if RAW_DUCKDB_INCOMPLETE_PATH.exists():
            RAW_DUCKDB_INCOMPLETE_PATH.unlink()

        if REEXTRAIR and RAW_DUCKDB_PATH.exists():
            RAW_DUCKDB_PATH.unlink()

        logger.info("Conectando no IQS Oracle...")
        con_oracle = conectar_oracle()

        logger.info("Criando DuckDB bruto temporario: %s", RAW_DUCKDB_INCOMPLETE_PATH)
        con_duck = duckdb.connect(str(RAW_DUCKDB_INCOMPLETE_PATH))
        con_duck.execute(f"SET temp_directory = {sql_literal(TEMP_DIR.as_posix())}")
        con_duck.execute("DROP TABLE IF EXISTS hiadms_raw")

        primeiro_lote = True
        total = 0

        try:
            for pdf in pd.read_sql_query(
                SQL_EXTRACAO,
                con_oracle,
                params={"anomes": ANOMES},
                chunksize=chunksize,
            ):
                if pdf.empty:
                    continue

                df = pl.from_pandas(pdf)
                con_duck.register("lote_tmp", df.to_arrow())

                if primeiro_lote:
                    con_duck.execute("CREATE TABLE hiadms_raw AS SELECT * FROM lote_tmp")
                    primeiro_lote = False
                else:
                    con_duck.execute("INSERT INTO hiadms_raw SELECT * FROM lote_tmp")

                total += len(df)
                logger.info("Extraidos: %s", f"{total:,}")
        finally:
            con_oracle.close()

        if primeiro_lote:
            con_duck.close()
            raise RuntimeError("Nenhum registro extraido do IQS.")

        con_duck.execute("""
            CREATE INDEX IF NOT EXISTS idx_hiadms_key
            ON hiadms_raw(
                PID_OCOR_INTRP_ULT_HIADMS,
                NUM_SEQ_INTRP_CHVP_HIADMS,
                NUM_UC_UCI_CHVP_HIADMS
            )
        """)

        total_validado = con_duck.execute("SELECT COUNT(*) FROM hiadms_raw").fetchone()[0]
        con_duck.close()

        if total_validado <= 0:
            raise RuntimeError("DuckDB bruto gerado sem registros.")

        RAW_DUCKDB_INCOMPLETE_PATH.rename(RAW_DUCKDB_PATH)
        finished_at = agora_iso()
        gravar_done(
            "extract",
            ANOMES,
            {
                "started_at": started_at,
                "finished_at": finished_at,
                "rows": total_validado,
                "duckdb_path": RAW_DUCKDB_PATH.as_posix(),
                "table": "hiadms_raw",
            },
        )
        logger.info("Extracao finalizada. Registros validados: %s", f"{total_validado:,}")


def registrar_raw_existente(logger=None):
    logger = logger or configurar_logger("extract", ANOMES)
    done = carregar_done("extract", ANOMES)

    if done:
        logger.info("Controle de extracao ja existe: %s", done.get("finished_at"))
        logger.info("DuckDB bruto registrado: %s", done.get("duckdb_path"))
        return

    if not RAW_DUCKDB_PATH.exists():
        raise FileNotFoundError(f"DuckDB bruto nao encontrado: {RAW_DUCKDB_PATH}")

    with lock_execucao("extract", ANOMES) as started_at:
        logger.info("Validando DuckDB bruto existente: %s", RAW_DUCKDB_PATH)
        con_duck = duckdb.connect(str(RAW_DUCKDB_PATH), read_only=True)

        try:
            total_validado = con_duck.execute("SELECT COUNT(*) FROM hiadms_raw").fetchone()[0]
        finally:
            con_duck.close()

        if total_validado <= 0:
            raise RuntimeError("DuckDB bruto existente nao possui registros em hiadms_raw.")

        gravar_done(
            "extract",
            ANOMES,
            {
                "started_at": started_at,
                "finished_at": agora_iso(),
                "rows": total_validado,
                "duckdb_path": RAW_DUCKDB_PATH.as_posix(),
                "table": "hiadms_raw",
                "registered_existing_raw": True,
            },
        )
        logger.info("Controle criado para bruto existente. Registros: %s", f"{total_validado:,}")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    logger = configurar_logger("extract", ANOMES)

    if REGISTRAR_RAW:
        logger.info("Registrando DuckDB bruto existente para ANOMES=%s", ANOMES)
        registrar_raw_existente(logger=logger)
    else:
        logger.info("Extraindo ANOMES=%s", ANOMES)
        extrair_iqs_para_duckdb(chunksize=100_000, logger=logger)

    logger.info("Fim.")

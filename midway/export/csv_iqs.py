import os
from pathlib import Path

import duckdb
from dotenv import load_dotenv

from midway.controle_execucao import configurar_logger
from midway.transform.tratamento import (
    ANOMES,
    EXPORT_DIR,
    PROCESSED_DUCKDB_PATH,
    RAW_DUCKDB_PATH,
    criar_tabela_exportacao_iqs,
    exportar_arquivos_iqs,
    exportar_mapeamento_layout_iqs,
    exportar_resumo_iqs,
    sql_literal,
)


load_dotenv()


def exportar_sem_reprocessar():
    logger = configurar_logger("exportar", ANOMES)
    logger.info("Exportando sem reprocessar ANOMES=%s", ANOMES)

    if not RAW_DUCKDB_PATH.exists():
        raise FileNotFoundError(f"DuckDB bruto nao encontrado: {RAW_DUCKDB_PATH}")

    if not PROCESSED_DUCKDB_PATH.exists():
        raise FileNotFoundError(f"DuckDB processado nao encontrado: {PROCESSED_DUCKDB_PATH}")

    con = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
    con.execute(f"ATTACH {sql_literal(RAW_DUCKDB_PATH.as_posix())} AS raw_db (READ_ONLY)")

    try:
        tabelas = {
            linha[0]
            for linha in con.execute("SHOW TABLES").fetchall()
        }

        if "adms_iqs_alterados" not in tabelas:
            raise RuntimeError("Tabela adms_iqs_alterados nao encontrada no DuckDB processado.")

        total_export = criar_tabela_exportacao_iqs(con, logger)
        regionais = con.execute("""
            SELECT DISTINCT REGIONAL_EXPORT
            FROM adms_iqs_export
            WHERE REGIONAL_EXPORT IS NOT NULL
            ORDER BY REGIONAL_EXPORT
        """).fetchall()

        if not regionais:
            logger.info("Nenhuma regional encontrada para exportar.")
            return

        arquivos_exportados = exportar_arquivos_iqs(
            con,
            regionais,
            EXPORT_DIR,
            "",
            logger,
        )
        mapeamento = exportar_mapeamento_layout_iqs(logger)
        resumo = exportar_resumo_iqs(arquivos_exportados, total_export)

        logger.info("Arquivos exportados: %s", len(arquivos_exportados))
        logger.info("Mapeamento do layout: %s", mapeamento)
        logger.info("Resumo da exportacao: %s", resumo)
    finally:
        con.close()


if __name__ == "__main__":
    exportar_sem_reprocessar()

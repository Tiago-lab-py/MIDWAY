import os
import sys
import logging
from dotenv import load_dotenv

from midway.controle_execucao import configurar_logger, valor_verdadeiro
from midway.extract.adms import registrar_raw_existente, extrair_iqs_para_duckdb
from midway.transform.tratamento import tratar_e_exportar_alterados
from midway.apuracao.previa import gerar_apuracao_previa
from midway.analytics.outlier_uc import main as gerar_outliers_uc

load_dotenv()

ANOMES = os.getenv("ANOMES", "202605")
REGISTRAR_RAW = valor_verdadeiro("REGISTRAR_RAW")
REPROCESSAR = valor_verdadeiro("REPROCESSAR")
REEXTRAIR = valor_verdadeiro("REEXTRAIR")

def main():
    """
    Orquestrador principal do pipeline ETL do MIDWAY.
    Encarregado de executar sequencialmente:
    1. Extração (ADMS -> RAW DuckDB)
    2. Tratamento (RAW -> Processed + Exportação de ajustes)
    3. Apuração (Processed -> Gold Tables e Apuração Prévia)
    """
    logger = configurar_logger("pipeline_etl", ANOMES)
    logger.info("=== INICIANDO PIPELINE ETL MIDWAY ===")
    logger.info(f"Competência (ANOMES): {ANOMES}")
    logger.info(f"Registrar RAW Existente: {REGISTRAR_RAW}")
    logger.info(f"Reprocessar Tratamento: {REPROCESSAR}")
    logger.info(f"Reextrair: {REEXTRAIR}")

    try:
        # FASE 1: Extração
        logger.info("--- [FASE 1/3] EXTRAÇÃO ---")
        if REGISTRAR_RAW:
            logger.info("Registrando DuckDB bruto existente.")
            registrar_raw_existente(logger=logger)
        else:
            logger.info("Extraindo dados para DuckDB.")
            extrair_iqs_para_duckdb(chunksize=100_000, logger=logger)
        
        # FASE 2: Tratamento
        logger.info("--- [FASE 2/3] TRATAMENTO ---")
        tratar_e_exportar_alterados(logger=logger)

        # FASE 3: Apuração
        logger.info("--- [FASE 3/3] APURAÇÃO ---")
        gerar_apuracao_previa(logger=logger)
        
        # FASE 3.1: Analytics (Outliers)
        logger.info("--- [FASE 3.1] ANALYTICS OUTLIERS ---")
        gerar_outliers_uc()

        logger.info("=== PIPELINE ETL CONCLUÍDO COM SUCESSO ===")

    except Exception as e:
        logger.error(f"Erro fatal durante a execução do pipeline ETL: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

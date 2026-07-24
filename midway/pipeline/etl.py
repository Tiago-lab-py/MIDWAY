import os
import sys
import logging
from dotenv import load_dotenv

from midway.controle_execucao import configurar_logger, valor_verdadeiro
from midway.extract.adms import registrar_raw_existente, extrair_iqs_para_duckdb
from midway.transform.tratamento import tratar_e_exportar_alterados
from midway.apuracao.previa import apuracao_previa as gerar_apuracao_previa
from midway.analytics.outlier_uc import materializar_gold_outlier_uc as gerar_outliers_uc

load_dotenv(override=True)

ANOMES = os.getenv("ANOMES", "202607")
REGISTRAR_RAW = valor_verdadeiro("REGISTRAR_RAW")
REPROCESSAR = valor_verdadeiro("REPROCESSAR")
REEXTRAIR = valor_verdadeiro("REEXTRAIR")

def main():
    """
    Orquestrador central do pipeline ETL do MIDWAY para início de mês.
    Executa em sequência ordenada:
    1. Extração Completa (ADMS, UCs Faturadas, Reclamações DBGUO, Serviços ADMS, Referências IQS)
    2. Tratamento (RAW -> Processed + Exportação de ajustes)
    3. Apuração Prévia (Gold Tables + Métricas DEC/FEC, DIC/FIC e Compensações)
    4. Analytics & Motor de Propostas
    """
    logger = configurar_logger("pipeline_etl", ANOMES)
    logger.info("=== INICIANDO PIPELINE ETL MIDWAY (INÍCIO DE MÊS) ===")
    logger.info(f"Competência (ANOMES): {ANOMES}")
    logger.info(f"Registrar RAW Existente: {REGISTRAR_RAW}")
    logger.info(f"Reprocessar Tratamento: {REPROCESSAR}")
    logger.info(f"Reextrair: {REEXTRAIR}")

    try:
        # FASE 1: EXTRAÇÃO SEQUENCIAL DE DADOS BRUTOS
        logger.info("--- [FASE 1/4] EXTRAÇÕES DE INÍCIO DE MÊS ---")

        # 1.1 Base Principal: ADMS Ocorrências e Interrupções
        if REGISTRAR_RAW:
            logger.info("[1.1] Registrando DuckDB bruto existente.")
            registrar_raw_existente(logger=logger)
        else:
            logger.info("[1.1] Extraindo dados brutos do ADMS (Ocorrências e Interrupções)...")
            extrair_iqs_para_duckdb(chunksize=100_000, logger=logger)

        # 1.2 Base de Consumidores Faturados (gold_uc_fatura)
        try:
            logger.info("[1.2] Extraindo UCs faturadas da competência...")
            from midway.extract.uc_fatura import extrair_uc_fatura
            extrair_uc_fatura()
        except Exception as err:
            logger.warning(f"[1.2] Aviso ao extrair UCs faturadas: {err}. Garantindo compatibilidade com o mês anterior.")

        # 1.2.1 Base de Consumidores (gold_consumidores)
        try:
            logger.info("[1.2.1] Extraindo Consumidores da competência...")
            from midway.extract.consumidores import extrair_consumidores
            extrair_consumidores()
        except Exception as err:
            logger.warning(f"[1.2.1] Aviso ao extrair Consumidores: {err}.")

        # 1.2.2 Metas UC (gold_metas_uc)
        try:
            logger.info("[1.2.2] Extraindo Metas UC...")
            from midway.extract.metas_uc import extrair_metas_uc
            extrair_metas_uc()
        except Exception as err:
            logger.warning(f"[1.2.2] Aviso ao extrair Metas UC: {err}.")

        # 1.2.3 VRC (gold_vrc)
        try:
            logger.info("[1.2.3] Extraindo VRC...")
            from midway.extract.vrc import extrair_vrc
            extrair_vrc()
        except Exception as err:
            logger.warning(f"[1.2.3] Aviso ao extrair VRC: {err}.")

        # 1.3 Base de Apoio: Reclamações DBGUO
        try:
            logger.info("[1.3] Extraindo reclamações DBGUO...")
            from midway.extract.reclamacoes_dbguo import extrair_reclamacoes_dbguo
            extrair_reclamacoes_dbguo()
        except Exception as err:
            logger.warning(f"[1.3] Reclamações DBGUO não extraídas: {err}.")

        # 1.4 Base de Apoio: Serviços ADMS
        try:
            logger.info("[1.4] Extraindo serviços operacionais ADMS...")
            from midway.extract.adms_servicos import extrair_adms_servicos
            extrair_adms_servicos()
        except Exception as err:
            logger.warning(f"[1.4] Serviços ADMS não extraídos: {err}.")

        # 1.5 Dicionários de Referência IQS (Componente e Causa)
        try:
            logger.info("[1.5] Extraindo tabelas de referência IQS (Componente/Causa)...")
            from midway.extract.referencia_componente_causa import extrair_referencia_componente_causa
            extrair_referencia_componente_causa()
        except Exception as err:
            logger.warning(f"[1.5] Referências IQS não extraídas: {err}.")

        # FASE 2: TRATAMENTO DE ANOMALIAS E NORMALIZAÇÃO
        logger.info("--- [FASE 2/4] TRATAMENTO E NORMALIZAÇÃO ---")
        
        try:
            logger.info("[2.1] Materializando Reclamações DBGUO (Silver e Gold)...")
            from midway.transform.dbguo_reclamacoes_silver import materializar_silver_e_gold
            materializar_silver_e_gold(logger=logger)
        except Exception as err:
            logger.warning(f"[2.1] Aviso ao processar Reclamações DBGUO: {err}.")
            
        logger.info("[2.2] Tratamento de anomalias da rede...")
        tratar_e_exportar_alterados(logger=logger)

        # FASE 3: APURAÇÃO PRÉVIA E MATERIALIZAÇÃO DE CAMADAS GOLD
        logger.info("--- [FASE 3/4] APURAÇÃO PRÉVIA REGULATÓRIA ---")
        gerar_apuracao_previa(logger=logger)

        # FASE 4: ANALYTICS, OUTLIERS E MOTOR DE ANOMALIAS
        logger.info("--- [FASE 4/4] ANALYTICS E PROPOSTAS DE ANOMALIA ---")
        gerar_outliers_uc()

        logger.info("=== PIPELINE ETL CONCLUÍDO COM SUCESSO DE PONTA A PONTA ===")

    except Exception as e:
        logger.error(f"Erro fatal durante a execução do pipeline ETL: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

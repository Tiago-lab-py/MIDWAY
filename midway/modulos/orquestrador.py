import json
import time
import logging
from typing import List, Tuple

from dotenv import load_dotenv
from sqlalchemy import text

from midway.controle_execucao import configurar_logger
from midway.db.postgres import create_postgres_engine

# Importar os módulos migrados
from midway.modulos.duracao_negativa import ModuloDuracaoNegativa
from midway.modulos.sobreposicao_uc import ModuloSobreposicaoUC
from midway.modulos.interrupcao_sem_uc import ModuloInterrupcaoSemUC
from midway.modulos.ajuste_inicio_manobra import ModuloAjusteInicioManobra
from midway.modulos.duplicidade_tipo_intrp import ModuloDuplicidadeTipoIntrp
from midway.modulos.agente_comp_causa import ModuloAgenteCompCausa
from midway.modulos.suspeita_falha_ra import ModuloSuspeitaFalhaRA
from midway.modulos.correcao_9282 import ModuloCorrecao9282
from midway.modulos.duracao_impacto import ModuloDuracaoImpacto
from midway.modulos.ressarcimento_atipico import ModuloRessarcimentoAtipico
from midway.modulos.reclamacoes_servicos import ModuloReclamacoesServicos
from midway.modulos.dia_critico_ise import ModuloDiaCriticoIse
from midway.modulos.base_modulo import PropostaTratamento, BaseModulo

logger = logging.getLogger(__name__)

# Configuração da ordem de execução
MODULOS_ATIVOS: List[BaseModulo] = [
    ModuloDuracaoNegativa(),
    ModuloSobreposicaoUC(),
    ModuloAjusteInicioManobra(),
    ModuloDuplicidadeTipoIntrp(),
    ModuloInterrupcaoSemUC(),
    ModuloAgenteCompCausa(),
    ModuloSuspeitaFalhaRA(),
    ModuloDuracaoImpacto(),
    ModuloRessarcimentoAtipico(),
    ModuloReclamacoesServicos(),
    ModuloDiaCriticoIse(),
    ModuloCorrecao9282() # Sempre por último, após todas as normalizações estruturais
]

def persistir_propostas_lote(propostas_com_codigo: List[Tuple[str, PropostaTratamento]], chunk_size: int = 10000) -> None:
    """Salva propostas no PostgreSQL usando inserção em lote veloz (execute_values)"""
    if not propostas_com_codigo:
        return
        
    engine = create_postgres_engine()
    
    dados_insercao = []
    for codigo_modulo, p in propostas_com_codigo:
        # Psycopg2 converte automaticamente listas do Python para arrays TEXT[] do Postgres
        dados_insercao.append((
            codigo_modulo,
            p.chave_negocio,
            json.dumps(p.evidencias),
            p.impacto,
            p.acao_sugerida,
            p.campos_iqs_afetados,
            p.exportacao_iqs
        ))
        
    total = len(dados_insercao)
    print(f"\nIniciando gravação ultrarrápida de {total} registros no Postgres...")
    
    from psycopg2.extras import execute_values
    
    start_time = time.time()
    try:
        raw_conn = engine.raw_connection()
        try:
            cur = raw_conn.cursor()
            execute_values(
                cur,
                """
                INSERT INTO ddcq.midway_propostas_tratamento 
                (codigo_modulo, chave_negocio, evidencias, impacto, acao_sugerida, campos_iqs_afetados, exportacao_iqs)
                VALUES %s
                """,
                dados_insercao,
                page_size=chunk_size
            )
            raw_conn.commit()
            cur.close()
        finally:
            raw_conn.close()
            
        elapsed = time.time() - start_time
        print(f"Gravação concluída com sucesso em {elapsed:.2f} segundos!\n")
    except Exception as e:
        print(f"Erro fatal ao gravar lotes no banco: {e}")

def orquestrar() -> None:
    load_dotenv()
    logger = configurar_logger("orquestrador_central", "Geral")
    logger.info("=== INICIANDO ORQUESTRAÇÃO DE ANOMALIAS ===")
    
    todas_propostas = []
    
    for modulo in MODULOS_ATIVOS:
        logger.info(f"Executando módulo: {modulo.codigo_modulo}...")
        try:
            propostas = modulo.detectar_anomalias()
            # Anexa o código do módulo na tupla para persistência
            for p in propostas:
                todas_propostas.append((modulo.codigo_modulo, p))
                
            logger.info(f"Módulo {modulo.codigo_modulo} finalizado.")
        except Exception as e:
            logger.error(f"Erro ao executar módulo {modulo.codigo_modulo}: {e}")
            
    logger.info(f"=== DETECÇÃO FINALIZADA. TOTAL GERAL: {len(todas_propostas)} ANOMALIAS ===")
    
    if todas_propostas:
        persistir_propostas_lote(todas_propostas)

if __name__ == "__main__":
    orquestrar()

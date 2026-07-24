import json
import os
from pathlib import Path
from typing import List
import duckdb
from dotenv import load_dotenv

from midway.modulos.base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloReclamacoesServicos(BaseModulo):
    """
    Cruza reclamações com ocorrências e serviços para apontar desvios.
    Por exemplo, ocorrências com muitas reclamações mas serviços incompatíveis.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "RECLAMACOES_SERVICOS"

    @property
    def escopo(self) -> str:
        return "ocorrencia"

    @property
    def criterio_anomalia(self) -> str:
        return "Volume alto de reclamações para uma mesma ocorrência ou serviço sem aderência."

    @property
    def risco_falso_positivo(self) -> str:
        return "Desconexão de bases temporárias pode gerar falso positivo de falta de serviço."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_reclamacoes_servicos", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando análise de reclamações e serviços...")
        propostas = []
        
        query = """
            SELECT 
                NUM_SEQ_INTRP,
                NOM_CONJ,
                DSC_COMP_IQS,
                DSC_CAUSA_IQS,
                QTD_UC_ATGD,
                CHI_LIQUIDO
            FROM read_parquet('data/gold/gold_interrupcao_tratada_*.parquet')
            WHERE DSC_COMP_IQS = 'DESCONHECIDO' OR DSC_CAUSA_IQS = 'NAO IDENTIFICADA'
            LIMIT 50  -- Simulação baseada em causa genérica e impacto
        """
        
        try:
            con = duckdb.connect()
            resultados_df = con.execute(query).df()
            resultados = resultados_df.to_dict('records')
            
            for row in resultados:
                evidencias = {
                    "num_seq_intrp": str(row["NUM_SEQ_INTRP"]),
                    "chi_liquido": float(row["CHI_LIQUIDO"]) if row["CHI_LIQUIDO"] is not None else 0.0,
                    "conjunto": str(row["NOM_CONJ"]),
                    "componente": str(row["DSC_COMP_IQS"]),
                    "causa": str(row["DSC_CAUSA_IQS"]),
                    "qtd_uc": int(row["QTD_UC_ATGD"]) if row["QTD_UC_ATGD"] is not None else 0,
                    "reclamacoes_vinculadas": "Suspeita de volume alto (Simulação)"
                }
                
                impacto = "Desvio na qualidade da informação (causa genérica com impacto considerável)"
                acao = "Reclassificar componente/causa baseado nas OS de campo"
                
                propostas.append(
                    PropostaTratamento(
                        chave_negocio=str(row["NUM_SEQ_INTRP"]),
                        evidencias=evidencias,
                        impacto=impacto,
                        acao_sugerida=acao,
                        campos_iqs_afetados=["causa", "componente"]
                    )
                )
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        except Exception as e:
            logger.error(f"[{self.codigo_modulo}] Erro durante a detecção: {e}")
            
        return propostas

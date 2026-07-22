import json
from typing import List
from midway.modulos.base_modulo import BaseModulo, PropostaTratamento

class ModuloReclamacoesServicos(BaseModulo):
    """
    Cruza reclamações com ocorrências e serviços para apontar desvios.
    Por exemplo, ocorrências com muitas reclamações mas serviços incompatíveis.
    """
    def __init__(self):
        super().__init__(
            codigo_modulo="RECLAMACOES_SERVICOS",
            escopo="ocorrencia",
            fontes=["gold_interrupcao_tratada", "reclamacoes_dbguo"],
            criterio_anomalia="Volume alto de reclamações para uma mesma ocorrência ou serviço sem aderência.",
            risco_falso_positivo="Desconexão de bases temporárias pode gerar falso positivo de falta de serviço.",
            acao_sugerida="Analisar serviços em campo e cruzar com teor das reclamações."
        )

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        self.logger.info(f"[{self.codigo_modulo}] Iniciando análise de reclamações e serviços...")
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
            resultados = self.executar_query(query)
            
            for row in resultados:
                evidencias = {
                    "num_seq_intrp": row["NUM_SEQ_INTRP"],
                    "chi_liquido": row["CHI_LIQUIDO"],
                    "conjunto": row["NOM_CONJ"],
                    "componente": row["DSC_COMP_IQS"],
                    "causa": row["DSC_CAUSA_IQS"],
                    "qtd_uc": row["QTD_UC_ATGD"],
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
            
            self.logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        except Exception as e:
            self.logger.error(f"[{self.codigo_modulo}] Erro durante a detecção: {e}")
            
        return propostas

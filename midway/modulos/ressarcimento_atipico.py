import json
from typing import List
from midway.modulos.base_modulo import BaseModulo, PropostaTratamento

class ModuloRessarcimentoAtipico(BaseModulo):
    """
    Detecta valores de ressarcimento incompatíveis com a granularidade correta ou
    duplicidade de compensação para a mesma UC.
    """
    def __init__(self):
        super().__init__(
            codigo_modulo="RESSARCIMENTO_ATIPICO",
            escopo="uc",
            fontes=["gold_ressarcimento_prodist"],
            criterio_anomalia="Duplicidade de compensação para mesma UC em várias ocorrências ou valores inflados.",
            risco_falso_positivo="Ressarcimento alto legítimo devido a violação massiva.",
            acao_sugerida="Revisar valores compensatórios associados à UC."
        )

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        self.logger.info(f"[{self.codigo_modulo}] Iniciando detecção de ressarcimento atípico...")
        propostas = []
        
        # Agrupa ressarcimento por UC e verifica se há valores anômalos ou múltiplas ocorrências
        query = """
            SELECT 
                NUM_UC,
                COUNT(DISTINCT PID_INTRP_SRVE) as qtd_ocorrencias,
                SUM(COMP_TOTAL_PRODIST) as soma_compensacao
            FROM read_parquet('data/gold/gold_ressarcimento_prodist_*.parquet')
            GROUP BY NUM_UC
            HAVING COUNT(DISTINCT PID_INTRP_SRVE) > 1 OR SUM(COMP_TOTAL_PRODIST) > 1000
        """
        
        try:
            resultados = self.executar_query(query)
            
            for row in resultados:
                evidencias = {
                    "num_uc": row["NUM_UC"],
                    "qtd_ocorrencias": row["qtd_ocorrencias"],
                    "soma_compensacao_estimada": round(row["soma_compensacao"], 2)
                }
                
                impacto = f"Compensação alta ou múltipla detectada: R$ {evidencias['soma_compensacao_estimada']}"
                acao = "Bloquear ranking e revisar alocação de ocorrências para a UC"
                
                propostas.append(
                    PropostaTratamento(
                        chave_negocio=str(row["NUM_UC"]),
                        evidencias=evidencias,
                        impacto=impacto,
                        acao_sugerida=acao,
                        campos_iqs_afetados=[]
                    )
                )
            
            self.logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        except Exception as e:
            self.logger.error(f"[{self.codigo_modulo}] Erro durante a detecção: {e}")
            
        return propostas

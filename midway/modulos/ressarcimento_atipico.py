import json
import os
from pathlib import Path
from typing import List
import duckdb
from dotenv import load_dotenv

from midway.modulos.base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloRessarcimentoAtipico(BaseModulo):
    """
    Detecta valores de ressarcimento incompatíveis com a granularidade correta ou
    duplicidade de compensação para a mesma UC.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "RESSARCIMENTO_ATIPICO"

    @property
    def escopo(self) -> str:
        return "uc"

    @property
    def criterio_anomalia(self) -> str:
        return "Duplicidade de compensação para mesma UC em várias ocorrências ou valores inflados."

    @property
    def risco_falso_positivo(self) -> str:
        return "Ressarcimento alto legítimo devido a violação massiva."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_ressarcimento_atipico", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção de ressarcimento atípico...")
        propostas = []
        
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
            con = duckdb.connect()
            resultados_df = con.execute(query).df()
            resultados = resultados_df.to_dict('records')
            
            for row in resultados:
                evidencias = {
                    "num_uc": str(row["NUM_UC"]),
                    "qtd_ocorrencias": int(row["qtd_ocorrencias"]),
                    "soma_compensacao_estimada": round(float(row["soma_compensacao"]), 2) if row["soma_compensacao"] is not None else 0.0
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
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        except Exception as e:
            logger.error(f"[{self.codigo_modulo}] Erro durante a detecção: {e}")
            
        return propostas

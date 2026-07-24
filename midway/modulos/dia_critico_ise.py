import json
import os
from pathlib import Path
from typing import List
import duckdb
from dotenv import load_dotenv

from midway.modulos.base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloDiaCriticoIse(BaseModulo):
    """
    Avalia a concentração de interrupções e o ISE para classificar dias críticos
    que merecem expurgo ou tratamento excepcional.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "DIA_CRITICO_ISE"

    @property
    def escopo(self) -> str:
        return "conjunto"

    @property
    def criterio_anomalia(self) -> str:
        return "Meta de Dia Crítico Sintética excedida por agrupamento regional ou conjunto."

    @property
    def risco_falso_positivo(self) -> str:
        return "Baixa densidade de UCs pode distorcer a meta sintética."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_dia_critico_ise", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando análise de dia crítico e ISE...")
        propostas = []
        
        # Leitura da lógica baseada na agregação diária de impacto
        query = """
            SELECT 
                NOM_CONJ,
                CAST(DAT_INI_INTRP AS DATE) as data_referencia,
                SUM(CHI_LIQUIDO) as total_chi,
                SUM(DUR_INTRP_MIN)/60 as horas_totais
            FROM read_parquet('data/gold/gold_interrupcao_tratada_*.parquet')
            GROUP BY NOM_CONJ, CAST(DAT_INI_INTRP AS DATE)
            HAVING SUM(CHI_LIQUIDO) > 1000 OR SUM(DUR_INTRP_MIN)/60 > 500
        """
        
        try:
            con = duckdb.connect()
            resultados_df = con.execute(query).df()
            resultados = resultados_df.to_dict('records')
            
            for row in resultados:
                evidencias = {
                    "conjunto": str(row["NOM_CONJ"]),
                    "data": str(row["data_referencia"]),
                    "total_chi": float(row["total_chi"]) if row["total_chi"] is not None else 0.0,
                    "horas_totais": round(float(row["horas_totais"]), 2) if row["horas_totais"] is not None else 0.0
                }
                
                impacto = f"Possível Dia Crítico detectado (Total CHI: {evidencias['total_chi']})"
                acao = "Analisar condições climáticas e aplicar regra de expurgo (se aplicável)"
                
                propostas.append(
                    PropostaTratamento(
                        chave_negocio=f"{row['NOM_CONJ']}_{row['data_referencia']}",
                        evidencias=evidencias,
                        impacto=impacto,
                        acao_sugerida=acao,
                        campos_iqs_afetados=["dia_critico_expurgo"]
                    )
                )
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        except Exception as e:
            logger.error(f"[{self.codigo_modulo}] Erro durante a detecção: {e}")
            
        return propostas

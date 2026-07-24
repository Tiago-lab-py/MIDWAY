from typing import List
import os
from pathlib import Path
import duckdb
from dotenv import load_dotenv

from midway.modulos.base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloDuracaoImpacto(BaseModulo):
    """
    Detecta interrupções/ocorrências com impactos suspeitamente altos:
    duração extrema, CHI elevado, etc.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "DURACAO_IMPACTO"

    @property
    def escopo(self) -> str:
        return "interrupcao"

    @property
    def criterio_anomalia(self) -> str:
        return "Duração da interrupção excede 72 horas ou CHI líquido muito alto (> 100)."

    @property
    def risco_falso_positivo(self) -> str:
        return "Eventos climáticos extremos podem justificar impactos imensos legitimamente."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_duracao_impacto", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção de duração/impactos anormais...")
        propostas = []
        
        query = """
            SELECT 
                NUM_SEQ_INTRP,
                NOM_CONJ,
                NOM_ALIM,
                DSC_COMP_IQS,
                DSC_CAUSA_IQS,
                DAT_INI_INTRP,
                DAT_FIM_INTRP,
                DUR_INTRP_MIN,
                QTD_UC_ATGD,
                CHI_LIQUIDO
            FROM gold_interrupcao_tratada
            WHERE DUR_INTRP_MIN > (72 * 60) OR COALESCE(CHI_LIQUIDO, 0) > 100
        """
        
        try:
            con = duckdb.connect()
            # duckdb uses dict fetch
            resultados_df = con.execute(query).df()
            resultados = resultados_df.to_dict('records')
            
            for row in resultados:
                evidencias = {
                    "duracao_horas": round(float(row["DUR_INTRP_MIN"]) / 60, 2) if row["DUR_INTRP_MIN"] is not None else 0.0,
                    "chi_liquido": float(row["CHI_LIQUIDO"]) if row["CHI_LIQUIDO"] is not None else 0.0,
                    "qtd_uc": int(row["QTD_UC_ATGD"]) if row["QTD_UC_ATGD"] is not None else 0,
                    "inicio": str(row["DAT_INI_INTRP"]),
                    "fim": str(row["DAT_FIM_INTRP"]),
                    "conjunto": str(row["NOM_CONJ"]),
                    "alimentador": str(row["NOM_ALIM"]),
                    "componente": str(row["DSC_COMP_IQS"]),
                    "causa": str(row["DSC_CAUSA_IQS"])
                }
                
                impacto = f"Impacto elevado: CHI={evidencias['chi_liquido']} | Dura={evidencias['duracao_horas']}h"
                acao = "Análise prioritária (cruzar serviços e reclamações)"
                
                propostas.append(
                    PropostaTratamento(
                        chave_negocio=str(row["NUM_SEQ_INTRP"]),
                        evidencias=evidencias,
                        impacto=impacto,
                        acao_sugerida=acao,
                        campos_iqs_afetados=["causa", "componente", "motivo_tratamento"]
                    )
                )
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        except Exception as e:
            logger.error(f"[{self.codigo_modulo}] Erro durante a detecção: {e}")
            
        return propostas

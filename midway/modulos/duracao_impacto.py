from typing import List
from midway.modulos.base_modulo import BaseModulo, PropostaTratamento

class ModuloDuracaoImpacto(BaseModulo):
    """
    Detecta interrupções/ocorrências com impactos suspeitamente altos:
    duração extrema, CHI elevado, etc.
    """
    def __init__(self):
        super().__init__(
            codigo_modulo="DURACAO_IMPACTO",
            escopo="interrupcao",
            fontes=["gold_interrupcao_tratada"],
            criterio_anomalia="Duração da interrupção excede 72 horas ou CHI líquido muito alto (> 100).",
            risco_falso_positivo="Eventos climáticos extremos podem justificar impactos imensos legitimamente.",
            acao_sugerida="Avaliar ocorrência detalhadamente cruzando serviços e reclamações."
        )

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        self.logger.info(f"[{self.codigo_modulo}] Iniciando detecção de duração/impactos anormais...")
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
            FROM read_parquet('data/gold/gold_interrupcao_tratada_*.parquet')
            WHERE DUR_INTRP_MIN > (72 * 60) OR COALESCE(CHI_LIQUIDO, 0) > 100
        """
        
        try:
            resultados = self.executar_query(query)
            
            for row in resultados:
                evidencias = {
                    "duracao_horas": round(row["DUR_INTRP_MIN"] / 60, 2),
                    "chi_liquido": row["CHI_LIQUIDO"],
                    "qtd_uc": row["QTD_UC_ATGD"],
                    "inicio": str(row["DAT_INI_INTRP"]),
                    "fim": str(row["DAT_FIM_INTRP"]),
                    "conjunto": row["NOM_CONJ"],
                    "alimentador": row["NOM_ALIM"],
                    "componente": row["DSC_COMP_IQS"],
                    "causa": row["DSC_CAUSA_IQS"]
                }
                
                impacto = f"Impacto elevado: CHI={row['CHI_LIQUIDO']} | Dura={evidencias['duracao_horas']}h"
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
            
            self.logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        except Exception as e:
            self.logger.error(f"[{self.codigo_modulo}] Erro durante a detecção: {e}")
            
        return propostas

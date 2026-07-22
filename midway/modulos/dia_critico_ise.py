import json
from typing import List
from midway.modulos.base_modulo import BaseModulo, PropostaTratamento

class ModuloDiaCriticoIse(BaseModulo):
    """
    Avalia a concentração de interrupções e o ISE para classificar dias críticos
    que merecem expurgo ou tratamento excepcional.
    """
    def __init__(self):
        super().__init__(
            codigo_modulo="DIA_CRITICO_ISE",
            escopo="conjunto",
            fontes=["gold_apuracao_uc"],
            criterio_anomalia="Meta de Dia Crítico Sintética excedida por agrupamento regional ou conjunto.",
            risco_falso_positivo="Baixa densidade de UCs pode distorcer a meta sintética.",
            acao_sugerida="Validar as interrupções do conjunto no dia indicado e classificar o expurgo."
        )

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        self.logger.info(f"[{self.codigo_modulo}] Iniciando análise de dia crítico e ISE...")
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
            resultados = self.executar_query(query)
            
            for row in resultados:
                evidencias = {
                    "conjunto": row["NOM_CONJ"],
                    "data": str(row["data_referencia"]),
                    "total_chi": row["total_chi"],
                    "horas_totais": round(row["horas_totais"], 2)
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
            
            self.logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        except Exception as e:
            self.logger.error(f"[{self.codigo_modulo}] Erro durante a detecção: {e}")
            
        return propostas

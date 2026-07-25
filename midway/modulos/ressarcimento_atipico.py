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
        return "ocorrencia"

    @property
    def criterio_anomalia(self) -> str:
        return "Ocorrências com alto valor de ressarcimento porém sem reclamações correspondentes ou com desproporção drástica."

    @property
    def risco_falso_positivo(self) -> str:
        return "Ressarcimento alto legítimo devido a violação massiva."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202607")
        logger = configurar_logger("modulo_ressarcimento_atipico", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção de ressarcimento atípico...")
        propostas = []
        
        try:
            base_dir = Path("data")
            processed_duckdb_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"
            if not processed_duckdb_path.exists():
                logger.error(f"DuckDB processado nao encontrado: {processed_duckdb_path}")
                return []

            con = duckdb.connect(str(processed_duckdb_path), read_only=True)
            try:
                tables = {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}
                
                if "gold_ressarcimento_prodist" not in tables or "adms_iqs_export" not in tables or "gold_reclamacao_uc_vinculada" not in tables:
                    logger.warning(f"[{self.codigo_modulo}] Tabelas necessárias (gold_ressarcimento_prodist, adms_iqs_export, gold_reclamacao_uc_vinculada) não encontradas. Ignorando detecção.")
                    return []

                query = """
                    WITH iqs_distinto AS (
                        SELECT DISTINCT
                            CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                            CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                            CAST(NUM_UC_UCI AS VARCHAR) AS NUM_UC_UCI
                        FROM adms_iqs_export
                        WHERE NUM_OCORRENCIA_ADMS IS NOT NULL
                          AND NUM_SEQ_INTRP IS NOT NULL
                          AND NUM_UC_UCI IS NOT NULL
                    ),
                    ressarcimento_distinto AS (
                        SELECT
                            CAST(NUM_UC AS VARCHAR) AS NUM_UC,
                            CAST(PID_INTRP_SRVE AS VARCHAR) AS NUM_SEQ_INTRP,
                            SUM(COALESCE(COMP_TOTAL_PRODIST, 0)) AS COMP_TOTAL_PRODIST
                        FROM gold_ressarcimento_prodist
                        WHERE COALESCE(COMP_TOTAL_PRODIST, 0) > 0
                        GROUP BY CAST(NUM_UC AS VARCHAR), CAST(PID_INTRP_SRVE AS VARCHAR)
                    ),
                    ocorrencia_ressarcimento AS (
                        SELECT 
                            r.NUM_OCORRENCIA_ADMS,
                            r.NUM_SEQ_INTRP,
                            COUNT(DISTINCT r.NUM_UC_UCI) AS total_ucs_afetadas,
                            SUM(res.COMP_TOTAL_PRODIST) AS soma_compensacao
                        FROM iqs_distinto r
                        JOIN ressarcimento_distinto res 
                          ON res.NUM_UC = r.NUM_UC_UCI
                         AND res.NUM_SEQ_INTRP = r.NUM_SEQ_INTRP
                        GROUP BY r.NUM_OCORRENCIA_ADMS, r.NUM_SEQ_INTRP
                        HAVING SUM(res.COMP_TOTAL_PRODIST) > 1000
                    ),
                    ocorrencia_reclamacoes AS (
                        SELECT 
                            CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                            COUNT(DISTINCT ID_RECLAMACAO) AS qtd_reclamacoes
                        FROM gold_reclamacao_uc_vinculada
                        WHERE CLASSIFICACAO_VINCULO_RECLAMACAO <> 'SEM_OCORRENCIA_PROVAVEL'
                          AND NUM_OCORRENCIA_ADMS IS NOT NULL
                        GROUP BY CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)
                    )
                    SELECT 
                        o.NUM_OCORRENCIA_ADMS,
                        o.NUM_SEQ_INTRP,
                        o.total_ucs_afetadas,
                        o.soma_compensacao,
                        COALESCE(rec.qtd_reclamacoes, 0) AS qtd_reclamacoes,
                        CASE 
                            WHEN COALESCE(rec.qtd_reclamacoes, 0) = 0 THEN 'Sem reclamações'
                            ELSE 'Baixa proporção de reclamações (' || ROUND((COALESCE(rec.qtd_reclamacoes, 0)::double / o.total_ucs_afetadas) * 100, 2) || '%)'
                        END AS motivo_atipico
                    FROM ocorrencia_ressarcimento o
                    LEFT JOIN ocorrencia_reclamacoes rec ON rec.NUM_OCORRENCIA_ADMS = o.NUM_OCORRENCIA_ADMS
                    WHERE COALESCE(rec.qtd_reclamacoes, 0) = 0
                       OR (o.total_ucs_afetadas >= 10 AND (COALESCE(rec.qtd_reclamacoes, 0)::double / o.total_ucs_afetadas) < 0.02)
                """

                resultados_df = con.execute(query).df()
            finally:
                con.close()
            resultados = resultados_df.to_dict('records')
            
            for row in resultados:
                evidencias = {
                    "num_ocorrencia": str(row["NUM_OCORRENCIA_ADMS"]),
                    "num_seq_intrp": str(row["NUM_SEQ_INTRP"]),
                    "total_ucs_afetadas": int(row["total_ucs_afetadas"]),
                    "soma_compensacao": round(float(row["soma_compensacao"]), 2) if row["soma_compensacao"] is not None else 0.0,
                    "qtd_reclamacoes": int(row["qtd_reclamacoes"]),
                    "motivo_atipico": str(row["motivo_atipico"])
                }
                
                impacto = f"Compensação atípica/inflada detectada (R$ {evidencias['soma_compensacao']}) para {evidencias['total_ucs_afetadas']} UCs afetadas e pouca ou nenhuma reclamação ({evidencias['qtd_reclamacoes']})."
                acao = "Bloquear ranking e auditar existência/comunicação da interrupção"
                
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

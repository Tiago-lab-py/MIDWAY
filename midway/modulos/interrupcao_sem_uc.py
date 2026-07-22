import os
from pathlib import Path
from typing import List

import duckdb
from dotenv import load_dotenv

from .base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloInterrupcaoSemUC(BaseModulo):
    """
    Identifica interrupções (Estado 4) onde todas as UCs associadas foram descartadas 
    por sobreposição (classificadas como 91/D), tornando a interrupção "vazia" (Estado 7).
    Ignora casos envolvidos em manobras (onde interrupção serve como pai/referência).
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "INTERRUPCAO_SEM_UC"
        
    @property
    def escopo(self) -> str:
        return "ocorrencia"

    @property
    def criterio_anomalia(self) -> str:
        return "Interrupção tem > 0 UCs, porém 100% delas estão com motivo 91/D e não há manobras dependentes."

    @property
    def risco_falso_positivo(self) -> str:
        return "Pode excluir interrupções que originaram manobras (pais). O código trata essa exceção."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_interrupcao_sem_uc", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção...")

        base_dir = Path("data")
        processed_duckdb_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"

        if not processed_duckdb_path.exists():
            logger.error(f"DuckDB processado nao encontrado: {processed_duckdb_path}")
            return []

        con = duckdb.connect(str(processed_duckdb_path), read_only=True)
        propostas = []
        
        try:
            tables = {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}

            if "adms_iqs_export" not in tables:
                logger.error("Tabela adms_iqs_export nao encontrada.")
                return []
            
            # O script original usa adms_iqs_export para contar as UCs e verificar os estados
            con.execute("""
                CREATE OR REPLACE TEMPORARY TABLE Auditoria_ESTADO_7 AS
                WITH interrupcoes AS (
                    SELECT
                        CAST(NUM_OCORRENCIA_ADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                        CAST(NUM_SEQ_INTRP AS VARCHAR) AS NUM_SEQ_INTRP,
                        CAST(NUM_INTRP_UCI AS VARCHAR) AS NUM_INTRP_UCI,
                        COUNT(*) AS QTD_UCS_TOTAL,
                        SUM(
                            CASE
                                WHEN TRIM(CAST(NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)) = '91'
                                 AND TRIM(CAST(INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)) = 'D'
                                THEN 1 ELSE 0
                            END
                        ) AS QTD_UCS_91_D,
                        SUM(
                            CASE
                                WHEN NULLIF(TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL
                                 AND TRIM(CAST(NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) NOT IN ('0', '0.0')
                                THEN 1 ELSE 0
                            END
                        ) AS QTD_UCS_COM_MANOBRA
                    FROM adms_iqs_export
                    WHERE TRIM(CAST(ESTADO_INTRP AS VARCHAR)) = '4'
                    GROUP BY
                        CAST(NUM_OCORRENCIA_ADMS AS VARCHAR),
                        CAST(NUM_SEQ_INTRP AS VARCHAR),
                        CAST(NUM_INTRP_UCI AS VARCHAR)
                ),
                referencias_manobra AS (
                    SELECT
                        p.NUM_OCORRENCIA_ADMS,
                        p.NUM_SEQ_INTRP,
                        p.NUM_INTRP_UCI,
                        COUNT(*) AS QTD_UCS_FILHAS_REFERENCIANDO
                    FROM interrupcoes p
                    JOIN adms_iqs_export f
                      ON CAST(f.NUM_SEQ_INTRP AS VARCHAR) <> p.NUM_SEQ_INTRP
                     AND NULLIF(TRIM(CAST(f.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)), '') IS NOT NULL
                     AND TRIM(CAST(f.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) NOT IN ('0', '0.0')
                     AND TRIM(CAST(f.NUM_INTRP_INIC_MANOBRA_UCI AS VARCHAR)) IN (
                            TRIM(p.NUM_INTRP_UCI),
                            TRIM(p.NUM_SEQ_INTRP)
                         )
                     AND TRIM(CAST(f.ESTADO_INTRP AS VARCHAR)) = '4'
                     AND NULLIF(TRIM(CAST(f.NUM_MOTIVO_TRAT_DIF_UCI AS VARCHAR)), '') IS NULL
                     AND NULLIF(TRIM(CAST(f.INDIC_SIT_PROCES_INDIC_UCI AS VARCHAR)), '') IS NULL
                    GROUP BY
                        p.NUM_OCORRENCIA_ADMS,
                        p.NUM_SEQ_INTRP,
                        p.NUM_INTRP_UCI
                )
                SELECT
                    i.NUM_OCORRENCIA_ADMS,
                    i.NUM_SEQ_INTRP,
                    i.QTD_UCS_TOTAL,
                    i.QTD_UCS_91_D,
                    i.QTD_UCS_COM_MANOBRA,
                    COALESCE(r.QTD_UCS_FILHAS_REFERENCIANDO, 0) AS QTD_UCS_FILHAS_REFERENCIANDO,
                    CASE
                        WHEN i.QTD_UCS_TOTAL > 0
                         AND i.QTD_UCS_91_D = i.QTD_UCS_TOTAL
                         AND i.QTD_UCS_COM_MANOBRA = 0
                         AND COALESCE(r.QTD_UCS_FILHAS_REFERENCIANDO, 0) = 0
                        THEN 'EXPORTAR_ESTADO_7_INTERRUPCAO_SEM_UC'
                        ELSE 'OK'
                    END AS RESULTADO_AUDITORIA
                FROM interrupcoes i
                LEFT JOIN referencias_manobra r
                  ON r.NUM_OCORRENCIA_ADMS = i.NUM_OCORRENCIA_ADMS
                 AND r.NUM_SEQ_INTRP = i.NUM_SEQ_INTRP
                 AND r.NUM_INTRP_UCI = i.NUM_INTRP_UCI
                WHERE i.QTD_UCS_TOTAL > 0
                  AND i.QTD_UCS_91_D = i.QTD_UCS_TOTAL
            """)
            
            df = con.execute("SELECT * FROM Auditoria_ESTADO_7 WHERE RESULTADO_AUDITORIA = 'EXPORTAR_ESTADO_7_INTERRUPCAO_SEM_UC'").df()
            records = df.to_dict(orient="records")
            
            for row in records:
                chave_negocio = f"{row['NUM_OCORRENCIA_ADMS']}-{row['NUM_SEQ_INTRP']}"
                
                evidencias = {
                    "num_ocorrencia": row['NUM_OCORRENCIA_ADMS'],
                    "num_seq_intrp": row['NUM_SEQ_INTRP'],
                    "qtd_ucs_total": row['QTD_UCS_TOTAL'],
                    "qtd_ucs_descartadas_91d": row['QTD_UCS_91_D']
                }
                
                propostas.append(PropostaTratamento(
                    chave_negocio=chave_negocio,
                    evidencias=evidencias,
                    impacto="Interrupção fantasma (Estado 4) não possui mais UCs válidas associadas.",
                    acao_sugerida="Alterar ESTADO_INTRP para 7, motivo 90 e indicador R.",
                    campos_iqs_afetados=["ESTADO_INTRP", "NUM_MOTIVO_TRAT_DIF_UCI", "INDIC_SIT_PROCES_INDIC_UCI"],
                    exportacao_iqs=None
                ))
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        finally:
            con.close()
            
        return propostas

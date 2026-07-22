import os
from pathlib import Path
from typing import List

import duckdb
from dotenv import load_dotenv

from .base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloAgenteCompCausa(BaseModulo):
    """
    Analisa ocorrências cruzando serviços de campo, componentes e reclamações,
    atribuindo um SCORE de risco para sugerir correção de COMPONENTE e CAUSA.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "AGENTE_COMP_CAUSA"
        
    @property
    def escopo(self) -> str:
        return "ocorrencia"

    @property
    def criterio_anomalia(self) -> str:
        return "Score heurístico >= 50 (baseado em dominância de serviços de campo e reclamações)."

    @property
    def risco_falso_positivo(self) -> str:
        return "Médio/Alto. As sugestões vêm de serviços anexos à ocorrência, mas a causa real pode ser diferente."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_agente_comp_causa", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção...")

        base_dir = Path("data")
        processed_duckdb_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"
        raw_servicos_path = base_dir / "raw" / f"adms_servicos_raw_{anomes}.duckdb"

        if not processed_duckdb_path.exists():
            logger.error(f"DuckDB processado nao encontrado: {processed_duckdb_path}")
            return []

        if not raw_servicos_path.exists():
            logger.error(f"DuckDB raw de serviços nao encontrado: {raw_servicos_path}")
            return []

        con = duckdb.connect(str(processed_duckdb_path), read_only=True)
        propostas = []
        
        try:
            # Verifica tabelas obrigatórias no processed
            tabelas = {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}
            required = {"gold_interrupcao_tratada", "gold_apuracao_uc", "gold_iqs_referencia_componente_causa"}
            
            if not required.issubset(tabelas):
                logger.error(f"Tabelas ausentes para Agente Comp/Causa. Necessário: {required}")
                return []
                
            # Faz o ATTACH do banco raw de serviços
            con.execute(f"ATTACH '{raw_servicos_path.resolve()}' AS serv_raw (READ_ONLY)")
            
            query = """
                WITH referencia AS (
                    SELECT DISTINCT
                        NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') AS COD_COMP,
                        NULLIF(TRIM(CAST(DESC_COMP AS VARCHAR)), '') AS DESC_COMP,
                        LPAD(NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), ''), 2, '0') AS COD_CAUSA,
                        NULLIF(TRIM(CAST(DESC_CAUSA AS VARCHAR)), '') AS DESC_CAUSA,
                        NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') AS COD_GRUPO_GCR,
                        NULLIF(TRIM(CAST(DESC_GRUPO_GCR AS VARCHAR)), '') AS DESC_GRUPO_GCR
                    FROM gold_iqs_referencia_componente_causa
                    WHERE NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') IS NOT NULL
                      AND NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), '') IS NOT NULL
                ),
                interrupcoes AS (
                    SELECT
                        TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                        MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                        MAX(LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_CAUSA_ATUAL,
                        MAX(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), '')) AS COD_COMP_ATUAL,
                        MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                        MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP
                    FROM gold_interrupcao_tratada
                    WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
                    GROUP BY 1
                ),
                apuracao AS (
                    SELECT
                        NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') AS NUM_OCORRENCIA_ADMS,
                        COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_APURAVEIS,
                        SUM(COALESCE(TRY_CAST(CHI_LIQUIDO AS DOUBLE), 0)) AS DIC_OCORRENCIA
                    FROM gold_apuracao_uc
                    WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
                    GROUP BY 1
                ),
                servico_pares AS (
                    SELECT
                        NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') AS NUM_SEQ_INTRP,
                        NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), '') AS COD_COMP_SERVICO,
                        LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') AS COD_CAUSA_SERVICO,
                        COUNT(*) AS LINHAS_SERVICO_PAR
                    FROM serv_raw.raw_adms_servicos
                    WHERE NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
                      AND NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), '') IS NOT NULL
                      AND NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), '') IS NOT NULL
                    GROUP BY 1, 2, 3
                ),
                servico_enriquecido AS (
                    SELECT
                        sp.*,
                        CASE WHEN ref.COD_COMP IS NOT NULL THEN 1 ELSE 0 END AS PAR_SERVICO_VALIDO,
                        ref.DESC_COMP AS DESC_COMP_SERVICO,
                        ref.DESC_CAUSA AS DESC_CAUSA_SERVICO
                    FROM servico_pares sp
                    LEFT JOIN referencia ref
                      ON ref.COD_COMP = sp.COD_COMP_SERVICO
                     AND ref.COD_CAUSA = sp.COD_CAUSA_SERVICO
                ),
                servico_totais AS (
                    SELECT
                        NUM_SEQ_INTRP,
                        SUM(LINHAS_SERVICO_PAR) AS LINHAS_SERVICO_TOTAL,
                        COUNT(*) AS QTD_PARES_SERVICO,
                        SUM(PAR_SERVICO_VALIDO) AS QTD_PARES_SERVICO_VALIDOS
                    FROM servico_enriquecido
                    GROUP BY 1
                ),
                servico_rank AS (
                    SELECT
                        se.*,
                        st.LINHAS_SERVICO_TOTAL,
                        st.QTD_PARES_SERVICO,
                        st.QTD_PARES_SERVICO_VALIDOS,
                        ROW_NUMBER() OVER (
                            PARTITION BY se.NUM_SEQ_INTRP
                            ORDER BY
                                se.PAR_SERVICO_VALIDO DESC,
                                se.LINHAS_SERVICO_PAR DESC,
                                se.COD_COMP_SERVICO,
                                se.COD_CAUSA_SERVICO
                        ) AS ORDEM_SERVICO
                    FROM servico_enriquecido se
                    JOIN servico_totais st
                      ON se.NUM_SEQ_INTRP = st.NUM_SEQ_INTRP
                ),
                reclamacoes AS (
                    SELECT
                        TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                        QTD_RECLAMACOES,
                        CAST(QTD_ADERENCIA_ALTA AS BIGINT) AS QTD_ADERENCIA_ALTA,
                        CAST(QTD_ADERENCIA_MEDIA AS BIGINT) AS QTD_ADERENCIA_MEDIA
                    FROM gold_reclamacao_ocorrencia_resumo
                    WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
                ),
                base AS (
                    SELECT
                        i.NUM_SEQ_INTRP,
                        i.NUM_OCORRENCIA_ADMS,
                        i.COD_COMP_ATUAL,
                        i.COD_CAUSA_ATUAL,
                        CASE WHEN ref_atual.COD_COMP IS NOT NULL THEN 1 ELSE 0 END AS PAR_ATUAL_VALIDO,
                        sr.COD_COMP_SERVICO AS COD_COMP_SUGERIDO,
                        sr.COD_CAUSA_SERVICO AS COD_CAUSA_SUGERIDA,
                        COALESCE(sr.PAR_SERVICO_VALIDO, 0) AS PAR_SERVICO_SUGERIDO_VALIDO,
                        CASE
                            WHEN COALESCE(sr.LINHAS_SERVICO_TOTAL, 0) > 0
                            THEN ROUND(100.0 * sr.LINHAS_SERVICO_PAR / sr.LINHAS_SERVICO_TOTAL, 2)
                            ELSE 0
                        END AS PCT_DOMINANCIA_SERVICO,
                        COALESCE(r.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
                        COALESCE(r.QTD_ADERENCIA_ALTA, 0) AS QTD_ADERENCIA_ALTA,
                        COALESCE(r.QTD_ADERENCIA_MEDIA, 0) AS QTD_ADERENCIA_MEDIA,
                        COALESCE(a.DIC_OCORRENCIA, 0) AS DIC_OCORRENCIA
                    FROM interrupcoes i
                    LEFT JOIN referencia ref_atual
                      ON ref_atual.COD_COMP = i.COD_COMP_ATUAL
                     AND ref_atual.COD_CAUSA = i.COD_CAUSA_ATUAL
                    LEFT JOIN servico_rank sr
                      ON sr.NUM_SEQ_INTRP = i.NUM_SEQ_INTRP
                     AND sr.ORDEM_SERVICO = 1
                    LEFT JOIN apuracao a
                      ON a.NUM_OCORRENCIA_ADMS = i.NUM_OCORRENCIA_ADMS
                    LEFT JOIN reclamacoes r
                      ON r.NUM_OCORRENCIA_ADMS = i.NUM_OCORRENCIA_ADMS
                ),
                escorada AS (
                    SELECT
                        *,
                        CASE
                            WHEN PAR_SERVICO_SUGERIDO_VALIDO = 1
                             AND PCT_DOMINANCIA_SERVICO >= 60
                             AND (
                                COALESCE(COD_COMP_SUGERIDO, '') <> COALESCE(COD_COMP_ATUAL, '')
                                OR COALESCE(COD_CAUSA_SUGERIDA, '') <> COALESCE(COD_CAUSA_ATUAL, '')
                             )
                                THEN 'AJUSTE_PROVAVEL_SERVICO'
                            WHEN PAR_ATUAL_VALIDO = 0
                                THEN 'PAR_ATUAL_FORA_REFERENCIA'
                            WHEN PAR_SERVICO_SUGERIDO_VALIDO = 1
                             AND (
                                COALESCE(COD_COMP_SUGERIDO, '') <> COALESCE(COD_COMP_ATUAL, '')
                                OR COALESCE(COD_CAUSA_SUGERIDA, '') <> COALESCE(COD_CAUSA_ATUAL, '')
                             )
                                THEN 'REVISAR_SERVICO_DIVERGENTE'
                            WHEN QTD_RECLAMACOES >= 10 AND (QTD_ADERENCIA_ALTA > 0 OR QTD_ADERENCIA_MEDIA > 0)
                                THEN 'REVISAR_RECLAMACAO_FORTE'
                            ELSE 'SEM_AJUSTE_PRIORITARIO'
                        END AS DECISAO_AGENTE,
                        LEAST(
                            100,
                            CASE WHEN PAR_SERVICO_SUGERIDO_VALIDO = 1
                                   AND (
                                        COALESCE(COD_COMP_SUGERIDO, '') <> COALESCE(COD_COMP_ATUAL, '')
                                        OR COALESCE(COD_CAUSA_SUGERIDA, '') <> COALESCE(COD_CAUSA_ATUAL, '')
                                   )
                                THEN 45 ELSE 0 END
                            + CASE WHEN PCT_DOMINANCIA_SERVICO >= 80 THEN 15 WHEN PCT_DOMINANCIA_SERVICO >= 60 THEN 10 ELSE 0 END
                            + CASE WHEN PAR_ATUAL_VALIDO = 0 THEN 20 ELSE 0 END
                            + CASE WHEN QTD_RECLAMACOES >= 10 THEN 10 WHEN QTD_RECLAMACOES >= 3 THEN 5 ELSE 0 END
                            + CASE WHEN QTD_ADERENCIA_ALTA > 0 THEN 10 WHEN QTD_ADERENCIA_MEDIA > 0 THEN 5 ELSE 0 END
                            + CASE WHEN DIC_OCORRENCIA >= 100 THEN 10 WHEN DIC_OCORRENCIA >= 20 THEN 5 ELSE 0 END
                        ) AS SCORE_AGENTE
                    FROM base
                )
                SELECT * FROM escorada
                WHERE SCORE_AGENTE >= 50
                  AND DECISAO_AGENTE <> 'SEM_AJUSTE_PRIORITARIO'
                  AND PAR_SERVICO_SUGERIDO_VALIDO = 1
            """
            
            df = con.execute(query).df()
            records = df.to_dict(orient="records")
            
            for row in records:
                chave_negocio = str(row['NUM_SEQ_INTRP'])
                
                evidencias = {
                    "num_ocorrencia": str(row['NUM_OCORRENCIA_ADMS']),
                    "num_seq_intrp": str(row['NUM_SEQ_INTRP']),
                    "comp_causa_atual": f"{row['COD_COMP_ATUAL']}/{row['COD_CAUSA_ATUAL']}",
                    "comp_causa_sugerido": f"{row['COD_COMP_SUGERIDO']}/{row['COD_CAUSA_SUGERIDA']}",
                    "score_agente": row['SCORE_AGENTE'],
                    "decisao": str(row['DECISAO_AGENTE']),
                    "pct_dominancia": row['PCT_DOMINANCIA_SERVICO']
                }
                
                propostas.append(PropostaTratamento(
                    chave_negocio=chave_negocio,
                    evidencias=evidencias,
                    impacto="Divergência entre Componente/Causa oficial e o que foi realizado nos serviços de campo.",
                    acao_sugerida="Substituir COD_COMP_INTRP e COD_CAUSA_INTRP pelos sugeridos pelo Agente.",
                    campos_iqs_afetados=["COD_COMP_INTRP", "COD_CAUSA_INTRP", "VALID_POS_OPERACAO"],
                    exportacao_iqs=None
                ))
            
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        finally:
            con.close()
            
        return propostas

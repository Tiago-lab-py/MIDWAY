import os
from pathlib import Path
from typing import List

import duckdb
import pandas as pd
from dotenv import load_dotenv

from .base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

class ModuloSuspeitaFalhaRA(BaseModulo):
    """
    Identifica suspeitas de falha de comunicação em Religadores Automáticos (RA)
    baseado no número de ocorrências, compensações geradas e ausência de reclamações proporcionais.
    Este módulo gera apenas alertas (não altera IQS automaticamente).
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "SUSPEITA_FALHA_RA"
        
    @property
    def escopo(self) -> str:
        return "equipamento_dia"

    @property
    def criterio_anomalia(self) -> str:
        return "Múltiplas operações do mesmo RA no dia, com alta compensação e baixa/nenhuma reclamação."

    @property
    def risco_falso_positivo(self) -> str:
        return "Alto. Alerta apenas para revisão em campo (não modifica dados do IQS)."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_suspeita_falha_ra", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção...")

        base_dir = Path("data")
        processed_duckdb_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"

        if not processed_duckdb_path.exists():
            logger.error(f"DuckDB processado nao encontrado: {processed_duckdb_path}")
            return []

        con = duckdb.connect(str(processed_duckdb_path), read_only=True)
        propostas = []
        
        try:
            # Tabelas obrigatórias
            tabelas = {row[0] for row in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall()}
            required = {"gold_interrupcao_tratada", "gold_apuracao_uc", "gold_ressarcimento_prodist", "gold_reclamacao_ocorrencia_resumo"}
            
            if not required.issubset(tabelas):
                logger.error(f"Tabelas ausentes. Necessário: {required}")
                return []

            # 1. Base query das ocorrências RA
            ocorrencias = con.execute("""
                WITH interrupcoes_ra AS (
                    SELECT
                        TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                        MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                        MAX(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), '')) AS REGIONAL,
                        MAX(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '')) AS CONJUNTO,
                        MAX(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')) AS ALIM_INTRP,
                        MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS NUM_OPER_CHV_INTRP,
                        MAX(NULLIF(TRIM(CAST(NUM_GEO_CHV_INTRP AS VARCHAR)), '')) AS NUM_GEO_CHV_INTRP,
                        MAX(NULLIF(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR)), '')) AS TIPO_CHV_INTRP,
                        MAX(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), '')) AS COD_COMP_INTRP,
                        MAX(LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_CAUSA_INTRP,
                        MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                        MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                        DATE(MIN(DATA_HORA_INIC_INTRP)) AS DIA_OPERACAO,
                        COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_INTERRUPCAO
                    FROM gold_interrupcao_tratada
                    WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
                      AND UPPER(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR))) = 'RA'
                      AND NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '') IS NOT NULL
                      AND DATA_HORA_INIC_INTRP IS NOT NULL
                    GROUP BY 1
                ),
                apuracao_seq AS (
                    SELECT
                        TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                        COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_APURAVEIS,
                        SUM(COALESCE(TRY_CAST(CI_LIQUIDO AS DOUBLE), 0)) AS CI_LIQUIDO,
                        SUM(COALESCE(TRY_CAST(CHI_LIQUIDO AS DOUBLE), 0)) AS CHI_LIQUIDO,
                        MAX(COALESCE(TRY_CAST(DURACAO_HORA AS DOUBLE), 0)) AS DURACAO_MAX_HORA
                    FROM gold_apuracao_uc
                    WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
                    GROUP BY 1
                ),
                reclamacoes AS (
                    SELECT
                        TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                        SUM(COALESCE(QTD_RECLAMACOES, 0)) AS QTD_RECLAMACOES,
                        SUM(COALESCE(QTD_UCS_RECLAMANTES, 0)) AS QTD_UCS_RECLAMANTES
                    FROM gold_reclamacao_ocorrencia_resumo
                    WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
                    GROUP BY 1
                ),
                uc_ocorrencia AS (
                    SELECT DISTINCT
                        TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                        TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                        TRIM(CAST(NUM_UC_UCI AS VARCHAR)) AS NUM_UC_UCI
                    FROM gold_apuracao_uc
                    WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
                      AND NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
                      AND NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
                ),
                uc_peso AS (
                    SELECT
                        NUM_UC_UCI,
                        COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS QTD_OCORRENCIAS_UC
                    FROM uc_ocorrencia
                    GROUP BY 1
                ),
                ressarcimento_seq AS (
                    SELECT
                        u.NUM_SEQ_INTRP,
                        SUM(COALESCE(r.COMP_FIC_PRODIST, 0) / NULLIF(COALESCE(p.QTD_OCORRENCIAS_UC, 1), 0)) AS COMP_FIC_ESTIMADA,
                        SUM(COALESCE(r.COMP_TOTAL_PRODIST, 0) / NULLIF(COALESCE(p.QTD_OCORRENCIAS_UC, 1), 0)) AS COMP_TOTAL_ESTIMADA,
                        COUNT(DISTINCT CASE WHEN COALESCE(r.COMP_FIC_PRODIST, 0) > 0 THEN u.NUM_UC_UCI END) AS UCS_COM_COMP_FIC,
                        COUNT(DISTINCT CASE WHEN COALESCE(r.COMP_TOTAL_PRODIST, 0) > 0 THEN u.NUM_UC_UCI END) AS UCS_COM_COMP_TOTAL
                    FROM uc_ocorrencia u
                    LEFT JOIN gold_ressarcimento_prodist r
                      ON u.NUM_UC_UCI = TRIM(CAST(r.UC AS VARCHAR))
                    LEFT JOIN uc_peso p
                      ON u.NUM_UC_UCI = p.NUM_UC_UCI
                    GROUP BY 1
                )
                SELECT
                    i.*,
                    COALESCE(a.UCS_APURAVEIS, i.UCS_INTERRUPCAO) AS UCS_APURAVEIS,
                    COALESCE(a.CI_LIQUIDO, 0) AS CI_LIQUIDO,
                    COALESCE(a.CHI_LIQUIDO, 0) AS CHI_LIQUIDO,
                    COALESCE(a.DURACAO_MAX_HORA, 0) AS DURACAO_MAX_HORA,
                    COALESCE(r.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
                    COALESCE(r.QTD_UCS_RECLAMANTES, 0) AS QTD_UCS_RECLAMANTES,
                    COALESCE(rs.COMP_FIC_ESTIMADA, 0) AS COMP_FIC_ESTIMADA,
                    COALESCE(rs.COMP_TOTAL_ESTIMADA, 0) AS COMP_TOTAL_ESTIMADA,
                    COALESCE(rs.UCS_COM_COMP_FIC, 0) AS UCS_COM_COMP_FIC,
                    COALESCE(rs.UCS_COM_COMP_TOTAL, 0) AS UCS_COM_COMP_TOTAL
                FROM interrupcoes_ra i
                LEFT JOIN apuracao_seq a
                  ON i.NUM_SEQ_INTRP = a.NUM_SEQ_INTRP
                LEFT JOIN reclamacoes r
                  ON i.NUM_OCORRENCIA_ADMS = r.NUM_OCORRENCIA_ADMS
                LEFT JOIN ressarcimento_seq rs
                  ON i.NUM_SEQ_INTRP = rs.NUM_SEQ_INTRP
            """).fetchdf()

            if ocorrencias.empty:
                logger.info(f"[{self.codigo_modulo}] Nenhuma ocorrência de RA.")
                return []

            # 2. Contexto Alimentador Dia
            min_fic = 3
            contexto_alimentador = con.execute(f"""
                WITH interrupcoes_ra AS (
                    SELECT
                        TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                        MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                        MAX(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), '')) AS REGIONAL,
                        MAX(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '')) AS CONJUNTO,
                        MAX(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')) AS ALIM_INTRP,
                        MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS NUM_OPER_CHV_INTRP,
                        DATE(MIN(DATA_HORA_INIC_INTRP)) AS DIA_OPERACAO
                    FROM gold_interrupcao_tratada
                    WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
                      AND UPPER(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR))) = 'RA'
                      AND NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '') IS NOT NULL
                      AND DATA_HORA_INIC_INTRP IS NOT NULL
                    GROUP BY 1
                ),
                reclamacoes AS (
                    SELECT
                        TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                        SUM(COALESCE(QTD_RECLAMACOES, 0)) AS QTD_RECLAMACOES,
                        SUM(COALESCE(QTD_UCS_RECLAMANTES, 0)) AS QTD_UCS_RECLAMANTES
                    FROM gold_reclamacao_ocorrencia_resumo
                    WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
                    GROUP BY 1
                ),
                ra_alimentador AS (
                    SELECT
                        REGIONAL,
                        CONJUNTO,
                        ALIM_INTRP,
                        DIA_OPERACAO,
                        COUNT(DISTINCT NUM_SEQ_INTRP) AS QTD_RA_ALIM_DIA,
                        COUNT(DISTINCT NUM_OPER_CHV_INTRP) AS QTD_EQUIPAMENTOS_RA_ALIM_DIA
                    FROM interrupcoes_ra
                    GROUP BY 1, 2, 3, 4
                ),
                ocorrencias_alimentador AS (
                    SELECT DISTINCT REGIONAL, CONJUNTO, ALIM_INTRP, DIA_OPERACAO, NUM_OCORRENCIA_ADMS
                    FROM interrupcoes_ra WHERE NUM_OCORRENCIA_ADMS IS NOT NULL
                ),
                reclamacoes_alimentador AS (
                    SELECT
                        o.REGIONAL, o.CONJUNTO, o.ALIM_INTRP, o.DIA_OPERACAO,
                        SUM(COALESCE(r.QTD_RECLAMACOES, 0)) AS QTD_RECLAMACOES_ALIM_DIA,
                        SUM(COALESCE(r.QTD_UCS_RECLAMANTES, 0)) AS QTD_UCS_RECLAMANTES_ALIM_DIA
                    FROM ocorrencias_alimentador o
                    LEFT JOIN reclamacoes r ON o.NUM_OCORRENCIA_ADMS = r.NUM_OCORRENCIA_ADMS
                    GROUP BY 1, 2, 3, 4
                ),
                fic_uc_alimentador AS (
                    SELECT
                        i.REGIONAL, i.CONJUNTO, i.ALIM_INTRP, i.DIA_OPERACAO,
                        TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)) AS NUM_UC_UCI,
                        COUNT(DISTINCT i.NUM_SEQ_INTRP) AS FIC_UC_ALIM_DIA
                    FROM gold_apuracao_uc a
                    JOIN interrupcoes_ra i ON TRIM(CAST(a.NUM_SEQ_INTRP AS VARCHAR)) = i.NUM_SEQ_INTRP
                    WHERE NULLIF(TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)), '') IS NOT NULL
                    GROUP BY 1, 2, 3, 4, 5
                ),
                fic_recorrente AS (
                    SELECT
                        REGIONAL, CONJUNTO, ALIM_INTRP, DIA_OPERACAO,
                        COUNT(DISTINCT NUM_UC_UCI) AS UCS_FIC_RECORRENTE_ALIM_DIA
                    FROM fic_uc_alimentador
                    WHERE FIC_UC_ALIM_DIA >= {min_fic}
                    GROUP BY 1, 2, 3, 4
                )
                SELECT
                    r.REGIONAL, r.CONJUNTO, r.ALIM_INTRP, r.DIA_OPERACAO,
                    r.QTD_RA_ALIM_DIA, r.QTD_EQUIPAMENTOS_RA_ALIM_DIA,
                    COALESCE(f.UCS_FIC_RECORRENTE_ALIM_DIA, 0) AS UCS_FIC_RECORRENTE_ALIM_DIA,
                    COALESCE(c.QTD_RECLAMACOES_ALIM_DIA, 0) AS QTD_RECLAMACOES_ALIM_DIA,
                    COALESCE(c.QTD_UCS_RECLAMANTES_ALIM_DIA, 0) AS QTD_UCS_RECLAMANTES_ALIM_DIA
                FROM ra_alimentador r
                LEFT JOIN fic_recorrente f ON r.REGIONAL = f.REGIONAL AND r.CONJUNTO = f.CONJUNTO AND r.ALIM_INTRP = f.ALIM_INTRP AND r.DIA_OPERACAO = f.DIA_OPERACAO
                LEFT JOIN reclamacoes_alimentador c ON r.REGIONAL = c.REGIONAL AND r.CONJUNTO = c.CONJUNTO AND r.ALIM_INTRP = c.ALIM_INTRP AND r.DIA_OPERACAO = c.DIA_OPERACAO
            """).fetchdf()

            # Mock serviços (para não estourar a memória num ATTACH extra se não for estritamente necessário no Python)
            ocorrencias["QTD_SERVICOS"] = 0
            ocorrencias["QTD_RECLAMACOES_SERVICO"] = 0
            ocorrencias["PRIMEIRA_SOLICITACAO_SERVICO"] = pd.NaT
            ocorrencias["ULTIMO_FECHAMENTO_SERVICO"] = pd.NaT

            grouped = (
                ocorrencias.groupby(["REGIONAL", "CONJUNTO", "ALIM_INTRP", "NUM_OPER_CHV_INTRP", "DIA_OPERACAO"], dropna=False, as_index=False)
                .agg(
                    QTD_OCORRENCIAS_RA=("NUM_SEQ_INTRP", "nunique"),
                    PRIMEIRA_INTERRUPCAO=("DATA_HORA_INIC_INTRP", "min"),
                    ULTIMA_INTERRUPCAO=("DATA_HORA_INIC_INTRP", "max"),
                    NUM_OCORRENCIAS_ADMS=("NUM_OCORRENCIA_ADMS", lambda values: ", ".join(sorted({str(value) for value in values if value}))),
                    CI_LIQUIDO_TOTAL=("CI_LIQUIDO", "sum"),
                    COMP_FIC_ESTIMADA=("COMP_FIC_ESTIMADA", "sum"),
                    QTD_OCORRENCIAS_COM_RECLAMACAO=("QTD_RECLAMACOES", lambda values: int((values > 0).sum())),
                    QTD_INTERRUPCOES_SEM_SERVICO=("QTD_SERVICOS", lambda values: int((values <= 0).sum())),
                )
            )
            
            grouped = grouped.merge(contexto_alimentador, on=["REGIONAL", "CONJUNTO", "ALIM_INTRP", "DIA_OPERACAO"], how="left").fillna(0)
            
            divisor_reclamacao = 250
            grouped["RECLAMACOES_MINIMAS_ALIM_DIA"] = grouped["UCS_FIC_RECORRENTE_ALIM_DIA"].apply(
                lambda value: int((int(value) + divisor_reclamacao - 1) // divisor_reclamacao) if int(value) >= divisor_reclamacao else 0
            )
            
            grouped["SINAL_ZERO_RECLAMACAO_EQUIPAMENTO"] = (grouped["QTD_OCORRENCIAS_COM_RECLAMACAO"].eq(0) & grouped["COMP_FIC_ESTIMADA"].ge(1.0))
            grouped["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"] = (grouped["RECLAMACOES_MINIMAS_ALIM_DIA"].gt(0) & grouped["QTD_RECLAMACOES_ALIM_DIA"].lt(grouped["RECLAMACOES_MINIMAS_ALIM_DIA"]))
            grouped["JANELA_MINUTOS"] = (pd.to_datetime(grouped["ULTIMA_INTERRUPCAO"]) - pd.to_datetime(grouped["PRIMEIRA_INTERRUPCAO"])).dt.total_seconds().fillna(0) / 60
            
            grouped["SCORE_SUSPEITA_RA"] = (
                (grouped["QTD_OCORRENCIAS_RA"] * 20)
                + grouped["CI_LIQUIDO_TOTAL"].clip(upper=100)
                + (grouped["COMP_FIC_ESTIMADA"] / 1000).clip(upper=40)
                + grouped["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"].astype(int) * 20
                + (grouped["JANELA_MINUTOS"].le(24 * 60).astype(int) * 10)
            ).clip(upper=100)
            
            grouped["CLASSIFICACAO"] = grouped.apply(
                lambda row: "CRITICA_BAIXA_RECLAMACAO_ALIM_CONJUNTO"
                if row["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"]
                else ("SUSPEITA_FORTE_FALHA_COMUNICACAO_RA" if row["QTD_OCORRENCIAS_RA"] >= 3 or row["COMP_FIC_ESTIMADA"] >= 1000 else "SUSPEITA_FALHA_COMUNICACAO_RA"),
                axis=1,
            )

            resumo = grouped[
                (grouped["QTD_OCORRENCIAS_RA"] >= 2)
                & (grouped["CI_LIQUIDO_TOTAL"] >= 10.0)
                & (grouped["SINAL_ZERO_RECLAMACAO_EQUIPAMENTO"] | grouped["SINAL_BAIXA_RECLAMACAO_ALIM_DIA"])
            ]
            
            records = resumo.to_dict(orient="records")
            for row in records:
                chave_negocio = f"{row['NUM_OPER_CHV_INTRP']}-{row['DIA_OPERACAO']}"
                
                evidencias = {
                    "equipamento": str(row['NUM_OPER_CHV_INTRP']),
                    "dia": str(row['DIA_OPERACAO']),
                    "qtd_ocorrencias_ra": row['QTD_OCORRENCIAS_RA'],
                    "classificacao": str(row['CLASSIFICACAO']),
                    "score_suspeita": row['SCORE_SUSPEITA_RA'],
                    "ocorrencias": str(row['NUM_OCORRENCIAS_ADMS'])
                }
                
                propostas.append(PropostaTratamento(
                    chave_negocio=chave_negocio,
                    evidencias=evidencias,
                    impacto="Operações sucessivas de Religador Automático sem reclamações proporcionais.",
                    acao_sugerida="Revisão operacional em campo e/ou validação no SCADA.",
                    campos_iqs_afetados=[],
                    exportacao_iqs=None
                ))
                
            logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias encontradas.")
            
        finally:
            con.close()
            
        return propostas

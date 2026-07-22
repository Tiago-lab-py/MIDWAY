import os
import unicodedata
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any

import duckdb
import pandas as pd
from dotenv import load_dotenv

from .base_modulo import BaseModulo, PropostaTratamento
from midway.controle_execucao import configurar_logger

TARGET_COMPONENTE = "92"
TARGET_CAUSA = "82"
TARGET_TIPO_CHAVE = "RA"

STOPWORDS = {
    "A", "AO", "AOS", "AS", "COM", "DA", "DAS", "DE", "DO", "DOS", "E", "EM", "ENERGIA",
    "ESPECIFICA", "FALTA", "IDENTIFICADA", "INTERRUPCAO", "NA", "NAO", "NO", "NOS", "O",
    "OCORRENCIA", "OS", "PARA", "POR", "PROVAVEL", "RECLAMACAO", "RA", "REDE", "SEM",
}

def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(char for char in normalized if not unicodedata.combining(char))

def _tokens(text: str) -> Set[str]:
    clean = _strip_accents(text).upper()
    for old, new in {"_": " ", "/": " ", "-": " ", ".": " ", ",": " ", ";": " ", "|": " ", "(": " ", ")": " "}.items():
        clean = clean.replace(old, new)
    tokens = {t for t in clean.split() if len(t) >= 3 and t not in STOPWORDS and not t.isdigit()}
    return _expand_tokens(tokens)

def _expand_tokens(tokens: Set[str]) -> Set[str]:
    expanded = set(tokens)
    if tokens & {"ARVORE", "GALHO", "PODA", "VEGETACAO", "VEGETACAO_REDE"}:
        expanded.update({"ARVORE", "GALHO", "PODA", "VEGETACAO"})
    if tokens & {"OSCILACAO", "PISCA", "PISCANDO", "TENSAO", "TENSÃO", "DESEQUILIBRIO"}:
        expanded.update({"OSCILACAO", "TENSAO", "DESEQUILIBRIO"})
    if tokens & {"DANO", "QUEIMA", "QUEIMADO", "EQUIPAMENTO", "DEFEITO", "FALHA"}:
        expanded.update({"DANO", "EQUIPAMENTO", "DEFEITO", "FALHA", "COMPONENTE"})
    if tokens & {"CABO", "FIO", "POSTE", "TRANSFORMADOR", "CONDUTOR", "RAMAL"}:
        expanded.update({"CABO", "FIO", "POSTE", "TRANSFORMADOR", "CONDUTOR", "RAMAL", "EQUIPAMENTO"})
    if tokens & {"FALTA", "DESLIGADO", "DESLIG", "APAGAO", "APAGADO"}:
        expanded.update({"INTERRUPCAO", "FALHA"})
    return expanded

def _reference_query() -> str:
    return """
        SELECT DISTINCT
            NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') AS COD_GRUPO_GCR,
            NULLIF(TRIM(CAST(DESC_GRUPO_GCR AS VARCHAR)), '') AS DESC_GRUPO_GCR,
            LPAD(NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), ''), 2, '0') AS COD_COMP,
            NULLIF(TRIM(CAST(DESC_COMP AS VARCHAR)), '') AS DESC_COMP,
            LPAD(NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), ''), 2, '0') AS COD_CAUSA,
            NULLIF(TRIM(CAST(DESC_CAUSA AS VARCHAR)), '') AS DESC_CAUSA,
            NULLIF(TRIM(CAST(GRUPO_COMPONENTE_REDE AS VARCHAR)), '') AS GRUPO_COMPONENTE_REDE,
            NULLIF(TRIM(CAST(COMPONENTE_REDE AS VARCHAR)), '') AS COMPONENTE_REDE,
            NULLIF(TRIM(CAST(CAUSA_REDE AS VARCHAR)), '') AS CAUSA_REDE
        FROM gold_iqs_referencia_componente_causa
        WHERE NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') IS NOT NULL
          AND NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), '') IS NOT NULL
    """

def _load_base(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(f"""
        WITH referencia AS ({_reference_query()}),
        alvo AS (
            SELECT
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                MAX(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '')) AS CONJUNTO,
                MAX(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), '')) AS REGIONAL,
                MAX(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')) AS ALIM_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS NUM_OPER_CHV_INTRP,
                MAX(NULLIF(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR)), '')) AS TIPO_CHV_INTRP,
                MAX(LPAD(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_COMP_ATUAL,
                MAX(LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_CAUSA_ATUAL,
                MAX(NULLIF(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR)), '')) AS VALID_POS_OPERACAO,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_INTERRUPCAO
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
              AND UPPER(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR))) = '{TARGET_TIPO_CHAVE}'
              AND LPAD(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), ''), 2, '0') = '{TARGET_COMPONENTE}'
              AND LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0') = '{TARGET_CAUSA}'
            GROUP BY 1
        ),
        apuracao AS (
            SELECT
                NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') AS NUM_OCORRENCIA_ADMS,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_APURAVEIS,
                SUM(COALESCE(TRY_CAST(CI_LIQUIDO AS DOUBLE), 0)) AS FIC_OCORRENCIA,
                SUM(COALESCE(TRY_CAST(CHI_LIQUIDO AS DOUBLE), 0)) AS DIC_OCORRENCIA
            FROM gold_apuracao_uc
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1
        ),
        reclamacoes AS (
            SELECT
                TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                QTD_RECLAMACOES, QTD_UCS_RECLAMANTES, TIPOS_RECLAMACAO_PROVAVEIS, CAUSAS_PROVAVEIS_RECLAMACAO,
                PREVIAS_CAUSA_RECLAMACAO, GRUPOS_CAUSA_IQS, GRUPOS_COMPONENTE_IQS, QTD_ADERENCIA_ALTA, QTD_ADERENCIA_MEDIA
            FROM gold_reclamacao_ocorrencia_resumo
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
        ),
        textos_reclamacao AS (
            SELECT
                TRIM(CAST(g.NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                LEFT(STRING_AGG(DISTINCT TRIM(COALESCE(TEXTO_RECLAMACAO, '') || ' ' || COALESCE(TEXTO_RETORNO, '')), ' '), 4000) AS TEXTOS_RECLAMACAO
            FROM gold_reclamacao_uc_vinculada g
            JOIN alvo ON alvo.NUM_OCORRENCIA_ADMS = TRIM(CAST(g.NUM_OCORRENCIA_ADMS AS VARCHAR))
            WHERE NULLIF(TRIM(CAST(g.NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1
        )
        SELECT
            alvo.*,
            ref.DESC_COMP AS DESC_COMP_ATUAL,
            ref.DESC_CAUSA AS DESC_CAUSA_ATUAL,
            COALESCE(apuracao.UCS_APURAVEIS, alvo.UCS_INTERRUPCAO) AS UCS_APURAVEIS,
            COALESCE(apuracao.FIC_OCORRENCIA, 0) AS FIC_OCORRENCIA,
            COALESCE(apuracao.DIC_OCORRENCIA, 0) AS DIC_OCORRENCIA,
            COALESCE(reclamacoes.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
            COALESCE(reclamacoes.QTD_UCS_RECLAMANTES, 0) AS QTD_UCS_RECLAMANTES,
            reclamacoes.TIPOS_RECLAMACAO_PROVAVEIS, reclamacoes.CAUSAS_PROVAVEIS_RECLAMACAO,
            reclamacoes.PREVIAS_CAUSA_RECLAMACAO, reclamacoes.GRUPOS_CAUSA_IQS, reclamacoes.GRUPOS_COMPONENTE_IQS,
            textos_reclamacao.TEXTOS_RECLAMACAO,
            COALESCE(reclamacoes.QTD_ADERENCIA_ALTA, 0) AS QTD_ADERENCIA_ALTA,
            COALESCE(reclamacoes.QTD_ADERENCIA_MEDIA, 0) AS QTD_ADERENCIA_MEDIA
        FROM alvo
        LEFT JOIN referencia ref ON ref.COD_COMP = alvo.COD_COMP_ATUAL AND ref.COD_CAUSA = alvo.COD_CAUSA_ATUAL
        LEFT JOIN apuracao ON alvo.NUM_OCORRENCIA_ADMS = apuracao.NUM_OCORRENCIA_ADMS
        LEFT JOIN reclamacoes ON alvo.NUM_OCORRENCIA_ADMS = reclamacoes.NUM_OCORRENCIA_ADMS
        LEFT JOIN textos_reclamacao ON alvo.NUM_OCORRENCIA_ADMS = textos_reclamacao.NUM_OCORRENCIA_ADMS
    """).fetchdf()

def _load_service_pairs(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(f"""
        WITH referencia AS ({_reference_query()}),
        alvo AS (
            SELECT DISTINCT TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
              AND UPPER(TRIM(CAST(TIPO_CHV_INTRP AS VARCHAR))) = '{TARGET_TIPO_CHAVE}'
              AND LPAD(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), ''), 2, '0') = '{TARGET_COMPONENTE}'
              AND LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0') = '{TARGET_CAUSA}'
        )
        SELECT
            alvo.NUM_SEQ_INTRP,
            LPAD(NULLIF(TRIM(CAST(serv.COD_COMP_SRVE AS VARCHAR)), ''), 2, '0') AS COD_COMP_SERVICO,
            LPAD(NULLIF(TRIM(CAST(serv.COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') AS COD_CAUSA_SERVICO,
            COUNT(*) AS LINHAS_SERVICO,
            COUNT(DISTINCT NULLIF(TRIM(CAST(serv.NUM_SEQ_SERV AS VARCHAR)), '')) AS QTD_SERVICOS,
            STRING_AGG(DISTINCT NULLIF(TRIM(CAST(serv.NUM_SEQ_SERV AS VARCHAR)), ''), ', ' ORDER BY NULLIF(TRIM(CAST(serv.NUM_SEQ_SERV AS VARCHAR)), '')) AS SERVICOS,
            MIN(serv.DTHR_INIC_SRV) AS PRIMEIRO_INICIO_SERVICO,
            MAX(serv.DTHR_FECH_SRV) AS ULTIMO_FECHAMENTO_SERVICO,
            ref.DESC_COMP AS DESC_COMP_SERVICO,
            ref.DESC_CAUSA AS DESC_CAUSA_SERVICO,
            ref.COD_GRUPO_GCR AS COD_GRUPO_GCR_SERVICO,
            ref.DESC_GRUPO_GCR AS DESC_GRUPO_GCR_SERVICO,
            CASE WHEN ref.COD_COMP IS NOT NULL THEN 1 ELSE 0 END AS PAR_SERVICO_VALIDO
        FROM alvo
        JOIN serv_raw.raw_adms_servicos serv ON alvo.NUM_SEQ_INTRP = TRIM(CAST(serv.PID_INTRP_SRVE AS VARCHAR))
        LEFT JOIN referencia ref ON ref.COD_COMP = LPAD(NULLIF(TRIM(CAST(serv.COD_COMP_SRVE AS VARCHAR)), ''), 2, '0') AND ref.COD_CAUSA = LPAD(NULLIF(TRIM(CAST(serv.COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0')
        WHERE NULLIF(TRIM(CAST(serv.PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
        GROUP BY alvo.NUM_SEQ_INTRP, COD_COMP_SERVICO, COD_CAUSA_SERVICO, ref.DESC_COMP, ref.DESC_CAUSA, ref.COD_GRUPO_GCR, ref.DESC_GRUPO_GCR, PAR_SERVICO_VALIDO
    """).fetchdf()

def _score_candidate(evidence_tokens: Set[str], candidate_tokens: Set[str]) -> Tuple[int, str]:
    overlap = sorted(evidence_tokens & candidate_tokens)
    score = len(overlap) * 8
    if evidence_tokens & {"VEGETACAO", "ARVORE", "GALHO", "PODA"} and candidate_tokens & {"VEGETACAO", "ARVORE", "GALHO", "PODA"}: score += 35
    if evidence_tokens & {"OSCILACAO", "TENSAO", "DESEQUILIBRIO"} and candidate_tokens & {"OSCILACAO", "TENSAO", "DESEQUILIBRIO"}: score += 35
    if evidence_tokens & {"DANO", "EQUIPAMENTO", "DEFEITO", "FALHA", "COMPONENTE"} and candidate_tokens & {"DANO", "EQUIPAMENTO", "DEFEITO", "FALHA", "COMPONENTE"}: score += 25
    if evidence_tokens & {"CABO", "FIO", "POSTE", "TRANSFORMADOR", "CONDUTOR", "RAMAL"} and candidate_tokens & {"CABO", "FIO", "POSTE", "TRANSFORMADOR", "CONDUTOR", "RAMAL"}: score += 20
    return min(score, 100), ", ".join(overlap)

def _suggest_from_complaint(row: pd.Series, reference_records: List[Dict[str, Any]], oscillation_candidate: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    evidence_text = " ".join(str(row.get(c) or "") for c in ["TEXTOS_RECLAMACAO", "TIPOS_RECLAMACAO_PROVAVEIS", "CAUSAS_PROVAVEIS_RECLAMACAO"])
    upper_evidence = _strip_accents(evidence_text).upper()
    if "OSCILACAO_TENSAO" in upper_evidence or "OSCILACAO TENSAO" in upper_evidence:
        if oscillation_candidate:
            return {
                "COD_COMP_SUGERIDO": oscillation_candidate["COD_COMP"], "COD_CAUSA_SUGERIDA": oscillation_candidate["COD_CAUSA"],
                "FONTE_SUGESTAO": "RECLAMACAO", "NIVEL_EVIDENCIA": "MEDIA", "SCORE_SUGESTAO": 75,
                "TERMOS_COINCIDENTES": "OSCILACAO_TENSAO", "JUSTIFICATIVA_ALGORITMO": "Oscilação de tensão identificada."
            }
    
    evidence_tokens = _tokens(evidence_text)
    if not evidence_tokens or not reference_records:
        return {"COD_COMP_SUGERIDO": "", "COD_CAUSA_SUGERIDA": "", "FONTE_SUGESTAO": "SEM_EVIDENCIA", "NIVEL_EVIDENCIA": "SEM_EVIDENCIA", "SCORE_SUGESTAO": 0}

    best = None
    for candidate in reference_records:
        score, terms = _score_candidate(evidence_tokens, candidate["TOKENS_REFERENCIA"])
        if score > 0:
            current = {
                "COD_COMP_SUGERIDO": candidate["COD_COMP"], "COD_CAUSA_SUGERIDA": candidate["COD_CAUSA"],
                "FONTE_SUGESTAO": "RECLAMACAO", "NIVEL_EVIDENCIA": "ALTA" if score >= 70 else "MEDIA" if score >= 35 else "BAIXA",
                "SCORE_SUGESTAO": score, "TERMOS_COINCIDENTES": terms, "JUSTIFICATIVA_ALGORITMO": "Coincidência textual na reclamação."
            }
            if best is None or current["SCORE_SUGESTAO"] > best["SCORE_SUGESTAO"]:
                best = current

    if best and best["SCORE_SUGESTAO"] >= 25: return best
    return {"COD_COMP_SUGERIDO": "", "COD_CAUSA_SUGERIDA": "", "FONTE_SUGESTAO": "RECLAMACAO_GENERICA", "NIVEL_EVIDENCIA": "BAIXA", "SCORE_SUGESTAO": best["SCORE_SUGESTAO"] if best else 0}

class ModuloCorrecao9282(BaseModulo):
    """
    Regra 9282: Transforma anomalias genéricas de Religador Automático (92/82) 
    em classificações corretas de campo usando NLP sobre serviços e reclamações.
    """
    
    @property
    def codigo_modulo(self) -> str:
        return "CORRECAO_9282"
        
    @property
    def escopo(self) -> str:
        return "interrupcao"

    @property
    def criterio_anomalia(self) -> str:
        return "TIPO_CHV_INTRP='RA', COD_COMP_INTRP='92', COD_CAUSA_INTRP='82'"

    @property
    def risco_falso_positivo(self) -> str:
        return "Baixo para evidências de serviços. Médio para NLP em reclamações."

    def detectar_anomalias(self) -> List[PropostaTratamento]:
        load_dotenv()
        anomes = os.getenv("ANOMES", "202606")
        logger = configurar_logger("modulo_correcao_9282", anomes)
        logger.info(f"[{self.codigo_modulo}] Iniciando detecção...")

        base_dir = Path("data")
        db_path = base_dir / "processed" / f"iqs_adms_processed_{anomes}.duckdb"
        raw_path = base_dir / "raw" / f"adms_servicos_raw_{anomes}.duckdb"

        if not db_path.exists() or not raw_path.exists():
            logger.error("Bancos DuckDB necessários ausentes.")
            return []

        propostas = []
        with duckdb.connect(str(db_path), read_only=True) as con:
            con.execute(f"ATTACH '{raw_path.resolve()}' AS serv_raw (READ_ONLY)")
            base = _load_base(con)
            if base.empty: return []
            
            service_pairs = _load_service_pairs(con)
            
            ref_raw = con.execute(_reference_query()).fetchdf()
            ref_raw["TEXTO_REFERENCIA"] = ref_raw[["DESC_GRUPO_GCR", "DESC_COMP", "DESC_CAUSA", "GRUPO_COMPONENTE_REDE", "COMPONENTE_REDE", "CAUSA_REDE"]].fillna("").agg(" ".join, axis=1)
            ref_raw["TOKENS_REFERENCIA"] = ref_raw["TEXTO_REFERENCIA"].map(_tokens)
            ref_prepared = ref_raw[~(ref_raw["COD_COMP"].astype(str).eq(TARGET_COMPONENTE) & ref_raw["COD_CAUSA"].astype(str).eq(TARGET_CAUSA))]
            ref_prepared = ref_prepared[~ref_prepared["COD_CAUSA"].astype(str).eq(TARGET_CAUSA)]
            
            ref_records = ref_prepared.to_dict("records")
            osc = [c for c in ref_records if str(c.get("COD_COMP")) == TARGET_COMPONENTE and str(c.get("COD_CAUSA")) == "38"]
            osc_cand = osc[0] if osc else None

            service_grouped = {str(k): v.copy() for k, v in service_pairs.groupby("NUM_SEQ_INTRP", dropna=False)}

            for _, row in base.iterrows():
                num_seq_intrp = str(row["NUM_SEQ_INTRP"])
                srv = service_grouped.get(num_seq_intrp, pd.DataFrame())
                
                sugestao = None
                if not srv.empty:
                    valid_srv = srv[srv["PAR_SERVICO_VALIDO"].fillna(0).astype(int).eq(1) & ~(srv["COD_COMP_SERVICO"].astype(str).eq(TARGET_COMPONENTE) & srv["COD_CAUSA_SERVICO"].astype(str).eq(TARGET_CAUSA))].copy()
                    if not valid_srv.empty:
                        valid_srv = valid_srv.sort_values(["QTD_SERVICOS", "LINHAS_SERVICO", "COD_COMP_SERVICO", "COD_CAUSA_SERVICO"], ascending=[False, False, True, True])
                        chosen = valid_srv.iloc[0]
                        sugestao = {
                            "COD_COMP_SUGERIDO": chosen["COD_COMP_SERVICO"], "COD_CAUSA_SUGERIDA": chosen["COD_CAUSA_SERVICO"],
                            "FONTE_SUGESTAO": "SERVICO", "NIVEL_EVIDENCIA": "ROBUSTA", "SCORE_SUGESTAO": 95
                        }

                if not sugestao:
                    sugestao = _suggest_from_complaint(row, ref_records, osc_cand)

                acao = "RECLASSIFICAR" if sugestao.get("FONTE_SUGESTAO") == "SERVICO" else "REVISAR_MANUAL"
                if not sugestao.get("COD_COMP_SUGERIDO"): acao = "MANTER_9282_SEM_EVIDENCIA"
                
                if acao in ("RECLASSIFICAR", "REVISAR_MANUAL"):
                    campos = ["COD_COMP_INTRP", "COD_CAUSA_INTRP", "VALID_POS_OPERACAO"] if acao == "RECLASSIFICAR" else []
                    
                    propostas.append(PropostaTratamento(
                        chave_negocio=num_seq_intrp,
                        evidencias={
                            "num_ocorrencia": str(row["NUM_OCORRENCIA_ADMS"]),
                            "comp_sugerido": str(sugestao.get("COD_COMP_SUGERIDO")),
                            "causa_sugerida": str(sugestao.get("COD_CAUSA_SUGERIDA")),
                            "fonte": str(sugestao.get("FONTE_SUGESTAO")),
                            "nivel_evidencia": str(sugestao.get("NIVEL_EVIDENCIA")),
                            "score": str(sugestao.get("SCORE_SUGESTAO"))
                        },
                        impacto=f"Classificação 92/82 genérica. Ação: {acao}",
                        acao_sugerida=f"Ajustar Componente/Causa para {sugestao.get('COD_COMP_SUGERIDO')}/{sugestao.get('COD_CAUSA_SUGERIDA')}",
                        campos_iqs_afetados=campos,
                        exportacao_iqs=None
                    ))

        logger.info(f"[{self.codigo_modulo}] Detecção concluída. {len(propostas)} anomalias avaliadas.")
        return propostas

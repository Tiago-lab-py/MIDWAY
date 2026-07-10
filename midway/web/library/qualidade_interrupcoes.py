from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from midway.web.library.shared import (
    DATA_DIR,
    format_number,
    require_table,
    show_metric_cards,
    sql_literal_for_streamlit,
    table_exists,
)


def adms_servicos_raw_path(anomes: str) -> Path:
    return DATA_DIR / "raw" / f"adms_servicos_raw_{anomes}.duckdb"


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _raw_servicos_exists(raw_path: Path) -> bool:
    if not raw_path.exists():
        return False

    with duckdb.connect(str(raw_path), read_only=True) as con:
        return (
            con.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'main'
                  AND table_name = 'raw_adms_servicos'
                """
            ).fetchone()[0]
            > 0
        )


def _referencia_componente_causa_cte(db_path: str) -> str:
    if table_exists(db_path, "gold_iqs_referencia_componente_causa"):
        return """
        referencia_comp_causa AS (
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
        """

    return """
        referencia_comp_causa AS (
            SELECT
                CAST(NULL AS VARCHAR) AS COD_COMP,
                CAST(NULL AS VARCHAR) AS DESC_COMP,
                CAST(NULL AS VARCHAR) AS COD_CAUSA,
                CAST(NULL AS VARCHAR) AS DESC_CAUSA,
                CAST(NULL AS VARCHAR) AS COD_GRUPO_GCR,
                CAST(NULL AS VARCHAR) AS DESC_GRUPO_GCR
            WHERE FALSE
        ),
        """


@st.cache_data(show_spinner=False)
def qualidade_overview(db_path: str, raw_path: str) -> pd.DataFrame:
    with duckdb.connect(db_path, read_only=True) as con:
        con.execute(f"ATTACH {_sql_literal(raw_path)} AS serv_raw (READ_ONLY)")
        return con.execute(
            """
            WITH interrupcoes AS (
                SELECT
                    TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                    MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS
                FROM gold_interrupcao_tratada
                WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
                GROUP BY 1
            ),
            servicos AS (
                SELECT
                    NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') AS NUM_SEQ_INTRP,
                    COUNT(*) AS LINHAS_SERVICO,
                    COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), '')) AS QTD_SERVICOS,
                    SUM(CASE WHEN LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') = '22' THEN 1 ELSE 0 END) AS QTD_CAUSA_22,
                    SUM(CASE WHEN LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') = '85' THEN 1 ELSE 0 END) AS QTD_CAUSA_85
                FROM serv_raw.raw_adms_servicos
                WHERE NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
                GROUP BY 1
            )
            SELECT
                COUNT(*) AS INTERRUPCOES_IQS,
                COUNT(*) FILTER (WHERE s.NUM_SEQ_INTRP IS NOT NULL) AS INTERRUPCOES_COM_SERVICO,
                COUNT(*) FILTER (WHERE r.NUM_OCORRENCIA_ADMS IS NOT NULL) AS INTERRUPCOES_COM_RECLAMACAO,
                COUNT(*) FILTER (WHERE COALESCE(s.QTD_CAUSA_22, 0) > 0) AS INTERRUPCOES_COM_CAUSA_22,
                COUNT(*) FILTER (WHERE COALESCE(s.QTD_CAUSA_85, 0) > 0) AS INTERRUPCOES_COM_CAUSA_85,
                SUM(COALESCE(s.QTD_SERVICOS, 0)) AS SERVICOS_DISTINTOS,
                SUM(COALESCE(r.QTD_RECLAMACOES, 0)) AS RECLAMACOES_VINCULADAS,
                SUM(COALESCE(r.QTD_UCS_RECLAMANTES, 0)) AS UCS_RECLAMANTES
            FROM interrupcoes i
            LEFT JOIN servicos s
              ON i.NUM_SEQ_INTRP = s.NUM_SEQ_INTRP
            LEFT JOIN gold_reclamacao_ocorrencia_resumo r
              ON i.NUM_OCORRENCIA_ADMS = TRIM(CAST(r.NUM_OCORRENCIA_ADMS AS VARCHAR))
            """
        ).fetchdf()


def _classification_sql() -> str:
    return """
        CASE
            WHEN COALESCE(QTD_CAUSA_85, 0) > 0 THEN 'SUSPEITA_IMPROCEDENTE'
            WHEN COALESCE(QTD_CAUSA_22, 0) > 0 THEN 'SUSPEITA_ATENDIDO_OUTRA_OCORRENCIA'
            WHEN COALESCE(QTD_INCONSISTENCIA_COMP_CAUSA, 0) > 0 THEN 'INCONSISTENCIA_COMPONENTE_CAUSA'
            WHEN COALESCE(QTD_RECLAMACOES, 0) >= 10 AND COALESCE(QTD_SERVICOS, 0) = 0
                THEN 'RECLAMACAO_FORTE_SEM_SERVICO'
            WHEN COALESCE(QTD_RECLAMACOES, 0) >= 10
                 AND (
                    COALESCE(ADERENCIA_RECLAMACAO_CAUSA_IQS, '') LIKE '%BAIXA%'
                    OR COALESCE(ADERENCIA_RECLAMACAO_CAUSA_IQS, '') LIKE '%MEDIA%'
                 )
                THEN 'RECLAMACAO_FORTE_REVISAR_CAUSA'
            WHEN COALESCE(QTD_SERVICOS, 0) > 1 THEN 'MULTIPLOS_SERVICOS_REVISAR'
            WHEN COALESCE(QTD_SERVICOS, 0) > 0 AND COALESCE(QTD_RECLAMACOES, 0) > 0
                THEN 'CAUSA_COMPONENTE_COM_EVIDENCIA'
            WHEN COALESCE(QTD_SERVICOS, 0) > 0 THEN 'SERVICO_SEM_RECLAMACAO'
            WHEN COALESCE(QTD_RECLAMACOES, 0) > 0 THEN 'RECLAMACAO_SEM_SERVICO'
            ELSE 'SEM_EVIDENCIA_COMPLEMENTAR'
        END
    """


def _score_sql() -> str:
    return """
        LEAST(
            100,
            CASE WHEN COALESCE(QTD_RECLAMACOES, 0) > 0 THEN 20 ELSE 0 END
            + CASE WHEN COALESCE(QTD_UCS_RECLAMANTES, 0) >= 3 THEN 15 ELSE 0 END
            + CASE WHEN COALESCE(QTD_SERVICOS, 0) > 0 THEN 20 ELSE 0 END
            + CASE WHEN COALESCE(QTD_CAUSA_22, 0) > 0 THEN 25 ELSE 0 END
            + CASE WHEN COALESCE(QTD_CAUSA_85, 0) > 0 THEN 25 ELSE 0 END
            + CASE WHEN COALESCE(QTD_INCONSISTENCIA_COMP_CAUSA, 0) > 0 THEN 25 ELSE 0 END
            + CASE WHEN COALESCE(QTD_SERVICOS, 0) > 1 THEN 10 ELSE 0 END
            + CASE
                WHEN COALESCE(CAUSAS_SERVICO, '') <> ''
                 AND COALESCE(COD_CAUSA_INTRP, '') <> ''
                 AND POSITION(COD_CAUSA_INTRP IN CAUSAS_SERVICO) = 0
                THEN 10 ELSE 0
              END
            + CASE
                WHEN COALESCE(COMPONENTES_SERVICO, '') <> ''
                 AND COALESCE(COD_COMP_INTRP, '') <> ''
                 AND POSITION(COD_COMP_INTRP IN COMPONENTES_SERVICO) = 0
                THEN 10 ELSE 0
              END
        )
    """


def _base_quality_query(db_path: str) -> str:
    return f"""
        WITH interrupcoes AS (
            SELECT
                TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '')) AS NUM_OCORRENCIA_ADMS,
                MAX(NULLIF(TRIM(CAST(COD_CONJTO_ELET_ANEEL_INTRP AS VARCHAR)), '')) AS CONJUNTO,
                MAX(NULLIF(TRIM(CAST(SIGLA_REGIONAL AS VARCHAR)), '')) AS REGIONAL,
                MAX(NULLIF(TRIM(CAST(ALIM_INTRP AS VARCHAR)), '')) AS ALIM_INTRP,
                MAX(NULLIF(TRIM(CAST(NUM_OPER_CHV_INTRP AS VARCHAR)), '')) AS NUM_OPER_CHV_INTRP,
                MAX(LPAD(NULLIF(TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ''), 2, '0')) AS COD_CAUSA_INTRP,
                MAX(NULLIF(TRIM(CAST(COD_COMP_INTRP AS VARCHAR)), '')) AS COD_COMP_INTRP,
                MAX(NULLIF(TRIM(CAST(VALID_POS_OPERACAO AS VARCHAR)), '')) AS VALID_POS_OPERACAO,
                MIN(DATA_HORA_INIC_INTRP) AS DATA_HORA_INIC_INTRP,
                MAX(DATA_HORA_FIM_INTRP) AS DATA_HORA_FIM_INTRP,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_UC_UCI AS VARCHAR)), '')) AS UCS_INTERRUPCAO
            FROM gold_interrupcao_tratada
            WHERE NULLIF(TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), '') IS NOT NULL
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
        servicos AS (
            SELECT
                NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') AS NUM_SEQ_INTRP,
                COUNT(*) AS LINHAS_SERVICO,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), '')) AS QTD_SERVICOS,
                STRING_AGG(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), ''), ', ' ORDER BY NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), '')) AS SERVICOS,
                STRING_AGG(DISTINCT LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0'), ', ' ORDER BY LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0')) AS CAUSAS_SERVICO,
                STRING_AGG(DISTINCT NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), ''), ', ' ORDER BY NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), '')) AS COMPONENTES_SERVICO,
                STRING_AGG(DISTINCT NULLIF(TRIM(CAST(NUM_ORG_EXEC_SRV AS VARCHAR)), ''), ', ' ORDER BY NULLIF(TRIM(CAST(NUM_ORG_EXEC_SRV AS VARCHAR)), '')) AS ORGAOS_EXECUTORES,
                MIN(DTHR_SOLIC_SRV) AS PRIMEIRA_SOLICITACAO_SERVICO,
                MIN(DTHR_DESPACH_SRV) AS PRIMEIRO_DESPACHO_SERVICO,
                MIN(DTHR_INIC_SRV) AS PRIMEIRO_INICIO_SERVICO,
                MAX(DTHR_TERM_SRV) AS ULTIMO_TERMINO_SERVICO,
                MAX(DTHR_FECH_SRV) AS ULTIMO_FECHAMENTO_SERVICO,
                SUM(CASE WHEN LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') = '22' THEN 1 ELSE 0 END) AS QTD_CAUSA_22,
                SUM(CASE WHEN LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') = '85' THEN 1 ELSE 0 END) AS QTD_CAUSA_85
            FROM serv_raw.raw_adms_servicos
            WHERE NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1
        ),
        servico_pares AS (
            SELECT DISTINCT
                NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') AS NUM_SEQ_INTRP,
                NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), '') AS COD_COMP_SERVICO,
                LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') AS COD_CAUSA_SERVICO
            FROM serv_raw.raw_adms_servicos
            WHERE NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), '') IS NOT NULL
        ),
        {_referencia_componente_causa_cte(db_path)}
        referencia_status AS (
            SELECT COUNT(*) AS QTD_REFERENCIAS_COMP_CAUSA
            FROM referencia_comp_causa
        ),
        ref_primeira_causa_comp AS (
            SELECT
                COD_COMP,
                MIN(COD_CAUSA) AS COD_CAUSA_SUGERIDA,
                ANY_VALUE(DESC_CAUSA) AS DESC_CAUSA_SUGERIDA
            FROM referencia_comp_causa
            WHERE COD_COMP IS NOT NULL
              AND COD_CAUSA IS NOT NULL
            GROUP BY COD_COMP
        ),
        ref_primeiro_comp_causa AS (
            SELECT
                COD_CAUSA,
                MIN(COD_COMP) AS COD_COMP_SUGERIDO,
                ANY_VALUE(DESC_COMP) AS DESC_COMP_SUGERIDO
            FROM referencia_comp_causa
            WHERE COD_COMP IS NOT NULL
              AND COD_CAUSA IS NOT NULL
            GROUP BY COD_CAUSA
        ),
        servico_consistencia AS (
            SELECT
                sp.NUM_SEQ_INTRP,
                COUNT(*) AS QTD_PARES_COMP_CAUSA_SERVICO,
                SUM(CASE WHEN rs.QTD_REFERENCIAS_COMP_CAUSA > 0 AND ref.COD_COMP IS NOT NULL THEN 1 ELSE 0 END) AS QTD_PARES_COMP_CAUSA_VALIDOS,
                SUM(CASE WHEN rs.QTD_REFERENCIAS_COMP_CAUSA > 0 AND ref.COD_COMP IS NULL THEN 1 ELSE 0 END) AS QTD_INCONSISTENCIA_COMP_CAUSA,
                STRING_AGG(
                    DISTINCT CASE
                        WHEN rs.QTD_REFERENCIAS_COMP_CAUSA > 0 AND ref.COD_COMP IS NULL THEN sp.COD_COMP_SERVICO || '/' || sp.COD_CAUSA_SERVICO
                    END,
                    ', '
                ) AS PARES_COMP_CAUSA_INCONSISTENTES,
                STRING_AGG(
                    DISTINCT CASE
                        WHEN rs.QTD_REFERENCIAS_COMP_CAUSA > 0 AND ref.COD_COMP IS NULL THEN
                            COALESCE(
                                CASE WHEN rpc.COD_CAUSA_SUGERIDA IS NOT NULL THEN sp.COD_COMP_SERVICO || '/' || rpc.COD_CAUSA_SUGERIDA END,
                                CASE WHEN rca.COD_COMP_SUGERIDO IS NOT NULL THEN rca.COD_COMP_SUGERIDO || '/' || sp.COD_CAUSA_SERVICO END
                            )
                    END,
                    ', '
                ) AS SUGESTAO_PARES_COMP_CAUSA,
                MIN(
                    CASE
                        WHEN rs.QTD_REFERENCIAS_COMP_CAUSA > 0 AND ref.COD_COMP IS NULL THEN COALESCE(sp.COD_COMP_SERVICO, rca.COD_COMP_SUGERIDO)
                    END
                ) AS SUGESTAO_COD_COMP_INTRP,
                MIN(
                    CASE
                        WHEN rs.QTD_REFERENCIAS_COMP_CAUSA > 0 AND ref.COD_COMP IS NULL THEN COALESCE(rpc.COD_CAUSA_SUGERIDA, sp.COD_CAUSA_SERVICO)
                    END
                ) AS SUGESTAO_COD_CAUSA_INTRP
            FROM servico_pares sp
            CROSS JOIN referencia_status rs
            LEFT JOIN referencia_comp_causa ref
              ON ref.COD_COMP = sp.COD_COMP_SERVICO
             AND ref.COD_CAUSA = sp.COD_CAUSA_SERVICO
            LEFT JOIN ref_primeira_causa_comp rpc
              ON rpc.COD_COMP = sp.COD_COMP_SERVICO
            LEFT JOIN ref_primeiro_comp_causa rca
              ON rca.COD_CAUSA = sp.COD_CAUSA_SERVICO
            GROUP BY sp.NUM_SEQ_INTRP
        ),
        reclamacoes AS (
            SELECT
                TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                QTD_RECLAMACOES,
                QTD_UCS_RECLAMANTES,
                TIPOS_RECLAMACAO_PROVAVEIS,
                CAUSAS_PROVAVEIS_RECLAMACAO,
                PREVIAS_CAUSA_RECLAMACAO,
                GRUPOS_CAUSA_IQS,
                GRUPOS_COMPONENTE_IQS,
                FIC_OCORRENCIA,
                DIC_OCORRENCIA,
                CAST(QTD_ADERENCIA_ALTA AS BIGINT) AS QTD_ADERENCIA_ALTA,
                CAST(QTD_ADERENCIA_MEDIA AS BIGINT) AS QTD_ADERENCIA_MEDIA,
                CASE
                    WHEN COALESCE(QTD_ADERENCIA_ALTA, 0) > 0 THEN 'ALTA'
                    WHEN COALESCE(QTD_ADERENCIA_MEDIA, 0) > 0 THEN 'MEDIA'
                    WHEN COALESCE(QTD_RECLAMACOES, 0) > 0 THEN 'BAIXA'
                    ELSE 'SEM_RECLAMACAO'
                END AS ADERENCIA_RECLAMACAO_CAUSA_IQS
            FROM gold_reclamacao_ocorrencia_resumo
            WHERE NULLIF(TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)), '') IS NOT NULL
        ),
        qualidade AS (
            SELECT
                i.NUM_SEQ_INTRP,
                i.NUM_OCORRENCIA_ADMS,
                i.CONJUNTO,
                i.REGIONAL,
                i.ALIM_INTRP,
                i.NUM_OPER_CHV_INTRP,
                i.COD_CAUSA_INTRP,
                i.COD_COMP_INTRP,
                i.VALID_POS_OPERACAO,
                i.DATA_HORA_INIC_INTRP,
                i.DATA_HORA_FIM_INTRP,
                COALESCE(a.UCS_APURAVEIS, i.UCS_INTERRUPCAO) AS UCS_APURAVEIS,
                COALESCE(s.LINHAS_SERVICO, 0) AS LINHAS_SERVICO,
                COALESCE(s.QTD_SERVICOS, 0) AS QTD_SERVICOS,
                s.SERVICOS,
                s.CAUSAS_SERVICO,
                s.COMPONENTES_SERVICO,
                s.ORGAOS_EXECUTORES,
                s.PRIMEIRA_SOLICITACAO_SERVICO,
                s.PRIMEIRO_DESPACHO_SERVICO,
                s.PRIMEIRO_INICIO_SERVICO,
                s.ULTIMO_TERMINO_SERVICO,
                s.ULTIMO_FECHAMENTO_SERVICO,
                COALESCE(s.QTD_CAUSA_22, 0) AS QTD_CAUSA_22,
                COALESCE(s.QTD_CAUSA_85, 0) AS QTD_CAUSA_85,
                COALESCE(sc.QTD_PARES_COMP_CAUSA_SERVICO, 0) AS QTD_PARES_COMP_CAUSA_SERVICO,
                COALESCE(sc.QTD_PARES_COMP_CAUSA_VALIDOS, 0) AS QTD_PARES_COMP_CAUSA_VALIDOS,
                COALESCE(sc.QTD_INCONSISTENCIA_COMP_CAUSA, 0) AS QTD_INCONSISTENCIA_COMP_CAUSA,
                sc.PARES_COMP_CAUSA_INCONSISTENTES,
                sc.SUGESTAO_PARES_COMP_CAUSA,
                COALESCE(sc.SUGESTAO_COD_COMP_INTRP, s.COMPONENTES_SERVICO) AS SUGESTAO_COD_COMP_INTRP,
                COALESCE(sc.SUGESTAO_COD_CAUSA_INTRP, s.CAUSAS_SERVICO) AS SUGESTAO_COD_CAUSA_INTRP,
                COALESCE(r.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
                COALESCE(r.QTD_UCS_RECLAMANTES, 0) AS QTD_UCS_RECLAMANTES,
                r.TIPOS_RECLAMACAO_PROVAVEIS,
                r.CAUSAS_PROVAVEIS_RECLAMACAO,
                r.PREVIAS_CAUSA_RECLAMACAO,
                r.GRUPOS_CAUSA_IQS,
                r.GRUPOS_COMPONENTE_IQS,
                COALESCE(a.FIC_OCORRENCIA, r.FIC_OCORRENCIA, 0) AS FIC_OCORRENCIA,
                COALESCE(a.DIC_OCORRENCIA, r.DIC_OCORRENCIA, 0) AS DIC_OCORRENCIA,
                COALESCE(r.QTD_ADERENCIA_ALTA, 0) AS QTD_ADERENCIA_ALTA,
                COALESCE(r.QTD_ADERENCIA_MEDIA, 0) AS QTD_ADERENCIA_MEDIA,
                COALESCE(r.ADERENCIA_RECLAMACAO_CAUSA_IQS, 'SEM_RECLAMACAO') AS ADERENCIA_RECLAMACAO_CAUSA_IQS
            FROM interrupcoes i
            LEFT JOIN apuracao a
              ON i.NUM_OCORRENCIA_ADMS = a.NUM_OCORRENCIA_ADMS
            LEFT JOIN servicos s
              ON i.NUM_SEQ_INTRP = s.NUM_SEQ_INTRP
            LEFT JOIN servico_consistencia sc
              ON i.NUM_SEQ_INTRP = sc.NUM_SEQ_INTRP
            LEFT JOIN reclamacoes r
              ON i.NUM_OCORRENCIA_ADMS = r.NUM_OCORRENCIA_ADMS
        )
        SELECT
            *,
            {_classification_sql()} AS CLASSIFICACAO_QUALIDADE,
            {_score_sql()} AS SCORE_QUALIDADE
        FROM qualidade
    """


@st.cache_data(show_spinner=False)
def qualidade_ranking(
    db_path: str,
    raw_path: str,
    classification: str,
    only_alerts: bool,
    occurrence: str,
    min_score: int,
    limit: int,
    valid_pos_operacao: str = "Todos",
) -> pd.DataFrame:
    filters = [f"SCORE_QUALIDADE >= {int(min_score)}"]
    if classification != "Todos":
        filters.append(f"CLASSIFICACAO_QUALIDADE = {sql_literal_for_streamlit(classification)}")
    if only_alerts:
        filters.append("CLASSIFICACAO_QUALIDADE NOT IN ('SEM_EVIDENCIA_COMPLEMENTAR', 'SERVICO_SEM_RECLAMACAO')")
    if occurrence.strip():
        value = occurrence.strip()
        filters.append(
            "("
            f"NUM_OCORRENCIA_ADMS = {sql_literal_for_streamlit(value)} "
            f"OR NUM_SEQ_INTRP = {sql_literal_for_streamlit(value)}"
            ")"
        )
    if valid_pos_operacao == "Somente validados (S)":
        filters.append("VALID_POS_OPERACAO = 'S'")
    elif valid_pos_operacao == "Somente pendentes (N)":
        filters.append("(VALID_POS_OPERACAO = 'N' OR VALID_POS_OPERACAO IS NULL)")

    where_clause = " AND ".join(filters)
    with duckdb.connect(db_path, read_only=True) as con:
        con.execute(f"ATTACH {_sql_literal(raw_path)} AS serv_raw (READ_ONLY)")
        return con.execute(
            f"""
            SELECT
                CLASSIFICACAO_QUALIDADE,
                SCORE_QUALIDADE,
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP,
                CONJUNTO,
                REGIONAL,
                ALIM_INTRP,
                NUM_OPER_CHV_INTRP,
                DATA_HORA_INIC_INTRP,
                DATA_HORA_FIM_INTRP,
                COD_CAUSA_INTRP,
                COD_COMP_INTRP,
                CAUSAS_SERVICO,
                COMPONENTES_SERVICO,
                QTD_PARES_COMP_CAUSA_SERVICO,
                QTD_PARES_COMP_CAUSA_VALIDOS,
                QTD_INCONSISTENCIA_COMP_CAUSA,
                PARES_COMP_CAUSA_INCONSISTENTES,
                SUGESTAO_PARES_COMP_CAUSA,
                SUGESTAO_COD_CAUSA_INTRP,
                SUGESTAO_COD_COMP_INTRP,
                QTD_SERVICOS,
                QTD_CAUSA_22,
                QTD_CAUSA_85,
                QTD_RECLAMACOES,
                QTD_UCS_RECLAMANTES,
                ADERENCIA_RECLAMACAO_CAUSA_IQS,
                TIPOS_RECLAMACAO_PROVAVEIS,
                CAUSAS_PROVAVEIS_RECLAMACAO,
                PREVIAS_CAUSA_RECLAMACAO,
                UCS_APURAVEIS,
                FIC_OCORRENCIA,
                DIC_OCORRENCIA,
                VALID_POS_OPERACAO,
                SERVICOS,
                ORGAOS_EXECUTORES,
                PRIMEIRO_INICIO_SERVICO,
                ULTIMO_FECHAMENTO_SERVICO
            FROM ({_base_quality_query(db_path)})
            WHERE {where_clause}
            ORDER BY
                SCORE_QUALIDADE DESC,
                QTD_INCONSISTENCIA_COMP_CAUSA DESC,
                QTD_RECLAMACOES DESC,
                QTD_SERVICOS DESC,
                DIC_OCORRENCIA DESC
            LIMIT {int(limit)}
            """
        ).fetchdf()


@st.cache_data(show_spinner=False)
def qualidade_por_classificacao(db_path: str, raw_path: str) -> pd.DataFrame:
    with duckdb.connect(db_path, read_only=True) as con:
        con.execute(f"ATTACH {_sql_literal(raw_path)} AS serv_raw (READ_ONLY)")
        return con.execute(
            f"""
            SELECT
                CLASSIFICACAO_QUALIDADE,
                COUNT(*) AS INTERRUPCOES,
                SUM(QTD_SERVICOS) AS SERVICOS,
                SUM(QTD_RECLAMACOES) AS RECLAMACOES,
                SUM(QTD_UCS_RECLAMANTES) AS UCS_RECLAMANTES,
                SUM(QTD_CAUSA_22) AS CAUSAS_22,
                SUM(QTD_CAUSA_85) AS CAUSAS_85,
                SUM(QTD_INCONSISTENCIA_COMP_CAUSA) AS INCONSISTENCIAS_COMP_CAUSA,
                AVG(SCORE_QUALIDADE) AS SCORE_MEDIO,
                SUM(DIC_OCORRENCIA) AS DIC_TOTAL
            FROM ({_base_quality_query(db_path)})
            GROUP BY 1
            ORDER BY
                MAX(SCORE_QUALIDADE) DESC,
                INTERRUPCOES DESC
            """
        ).fetchdf()


@st.cache_data(show_spinner=False)
def servicos_por_causa(db_path: str, raw_path: str, limit: int) -> pd.DataFrame:
    with duckdb.connect(db_path, read_only=True) as con:
        con.execute(f"ATTACH {_sql_literal(raw_path)} AS serv_raw (READ_ONLY)")
        return con.execute(
            f"""
            SELECT
                LPAD(NULLIF(TRIM(CAST(COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') AS COD_CAUSA_SRVE,
                NULLIF(TRIM(CAST(COD_COMP_SRVE AS VARCHAR)), '') AS COD_COMP_SRVE,
                NULLIF(TRIM(CAST(ESTADO_SERVICO_ACOMP AS VARCHAR)), '') AS ESTADO_SERVICO_ACOMP,
                COUNT(*) AS LINHAS,
                COUNT(DISTINCT NULLIF(TRIM(CAST(PID_INTRP_SRVE AS VARCHAR)), '')) AS INTERRUPCOES,
                COUNT(DISTINCT NULLIF(TRIM(CAST(NUM_SEQ_SERV AS VARCHAR)), '')) AS SERVICOS
            FROM serv_raw.raw_adms_servicos
            GROUP BY 1,2,3
            ORDER BY LINHAS DESC
            LIMIT {int(limit)}
            """
        ).fetchdf()


def show_qualidade_interrupcoes(anomes: str, db_path: str, sample_limit: int) -> None:
    st.subheader("Qualidade de Interrupções")
    st.caption(
        "Cruza interrupções IQS/ADMS, reclamações DBGUO e serviços ADMS para priorizar revisão de causa, componente, improcedência e duplicidade."
    )

    raw_path = adms_servicos_raw_path(anomes)
    if not _raw_servicos_exists(raw_path):
        st.info(
            "RAW de serviços ADMS não encontrado. Execute "
            "`run.bat extrair_adms_servicos` para gerar "
            f"`{raw_path}`."
        )
        return

    required_tables = ["gold_interrupcao_tratada", "gold_reclamacao_ocorrencia_resumo"]
    missing = [table for table in required_tables if not table_exists(db_path, table)]
    if missing:
        st.info(
            "Tabelas gold necessárias não encontradas: "
            + ", ".join(f"`{table}`" for table in missing)
            + ". Execute `run.bat apuracao_parcial` e `run.bat dbguo_reclamacoes`."
        )
        return

    overview = qualidade_overview(db_path, str(raw_path))
    if overview.empty:
        st.warning("Não foi possível calcular o resumo de qualidade.")
        return

    row = overview.iloc[0]
    show_metric_cards(
        [
            ("Interrupções IQS", format_number(row["INTERRUPCOES_IQS"], 0), None),
            ("Com serviço", format_number(row["INTERRUPCOES_COM_SERVICO"], 0), None),
            ("Com reclamação", format_number(row["INTERRUPCOES_COM_RECLAMACAO"], 0), None),
            ("Causa serviço 22", format_number(row["INTERRUPCOES_COM_CAUSA_22"], 0), "Atendido por outra ocorrência"),
            ("Causa serviço 85", format_number(row["INTERRUPCOES_COM_CAUSA_85"], 0), "Improcedente"),
            ("Serviços distintos", format_number(row["SERVICOS_DISTINTOS"], 0), None),
        ]
    )

    st.caption(f"RAW serviços: `{raw_path}`")

    tabs = st.tabs(["Ranking de revisão", "Resumo por classificação", "Serviços por causa"])

    with tabs[0]:
        col_class, col_score, col_flags, col_search = st.columns([2, 1, 1, 2])
        with col_class:
            classification = st.selectbox(
                "Classificação",
                [
                    "Todos",
                    "SUSPEITA_IMPROCEDENTE",
                    "SUSPEITA_ATENDIDO_OUTRA_OCORRENCIA",
                    "INCONSISTENCIA_COMPONENTE_CAUSA",
                    "RECLAMACAO_FORTE_SEM_SERVICO",
                    "RECLAMACAO_FORTE_REVISAR_CAUSA",
                    "MULTIPLOS_SERVICOS_REVISAR",
                    "CAUSA_COMPONENTE_COM_EVIDENCIA",
                    "RECLAMACAO_SEM_SERVICO",
                    "SERVICO_SEM_RECLAMACAO",
                    "SEM_EVIDENCIA_COMPLEMENTAR",
                ],
            )
        with col_score:
            min_score = st.slider("Score mínimo", 0, 100, 20, step=5)
        with col_flags:
            only_alerts = st.checkbox("Somente alertas", value=True)
        with col_search:
            occurrence = st.text_input("Ocorrência ou interrupção", value="", placeholder="Opcional")

        ranking = qualidade_ranking(
            db_path,
            str(raw_path),
            classification,
            only_alerts,
            occurrence,
            min_score,
            sample_limit,
        )
        if ranking.empty:
            st.success("Nenhuma interrupção encontrada para os filtros informados.")
        else:
            st.dataframe(
                ranking,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "SCORE_QUALIDADE": st.column_config.ProgressColumn("Score", min_value=0, max_value=100),
                    "DIC_OCORRENCIA": st.column_config.NumberColumn("DIC", format="%.3f"),
                    "FIC_OCORRENCIA": st.column_config.NumberColumn("FIC", format="%.3f"),
                },
            )
            st.download_button(
                "Baixar ranking de qualidade",
                ranking.to_csv(index=False, sep=";").encode("utf-8-sig"),
                file_name="qualidade_interrupcoes_ranking.csv",
                mime="text/csv",
            )

    with tabs[1]:
        resumo = qualidade_por_classificacao(db_path, str(raw_path))
        st.dataframe(
            resumo,
            use_container_width=True,
            hide_index=True,
            column_config={
                "SCORE_MEDIO": st.column_config.NumberColumn("Score médio", format="%.1f"),
                "DIC_TOTAL": st.column_config.NumberColumn("DIC total", format="%.3f"),
            },
        )
        st.download_button(
            "Baixar resumo por classificação",
            resumo.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="qualidade_interrupcoes_resumo.csv",
            mime="text/csv",
        )

    with tabs[2]:
        causas = servicos_por_causa(db_path, str(raw_path), sample_limit)
        st.dataframe(causas, use_container_width=True, hide_index=True)
        st.download_button(
            "Baixar serviços por causa",
            causas.to_csv(index=False, sep=";").encode("utf-8-sig"),
            file_name="servicos_adms_por_causa.csv",
            mime="text/csv",
        )

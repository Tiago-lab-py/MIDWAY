from __future__ import annotations

from pathlib import Path

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from midway.api.security import AuthUser, require_profiles
from midway.api.serialization import api_rows

router = APIRouter(prefix="/api/qualidade", tags=["qualidade"])


def _processed_path(anomes: str) -> Path:
    return Path("data/processed") / f"iqs_adms_processed_{anomes}.duckdb"


def _raw_services_path(anomes: str) -> Path:
    return Path("data/raw") / f"adms_servicos_raw_{anomes}.duckdb"


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _fetch_rows(con: duckdb.DuckDBPyConnection, sql: str, params: list[object]) -> list[dict[str, object]]:
    df = con.execute(sql, params).fetchdf()
    return api_rows(df.to_dict(orient="records"))


@router.get("/busca")
def busca_qualidade(
    tipo: str = Query("ocorrencia", pattern="^(ocorrencia|interrupcao|uc)$"),
    valor: str = Query(..., min_length=1),
    anomes: str = "202606",
    limit: int = Query(20, ge=1, le=100),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA")),
) -> list[dict[str, object]]:
    db_path = _processed_path(anomes)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"DuckDB processado não encontrado: {db_path}")

    valor_busca = valor.strip()
    if not valor_busca:
        raise HTTPException(status_code=400, detail="Informe um valor para busca.")

    if tipo == "ocorrencia":
        ocorrencias_sql = """
            SELECT ? AS NUM_OCORRENCIA_ADMS
            UNION
            SELECT DISTINCT NUM_OCORRENCIA_ADMS
            FROM gold_interrupcao_tratada
            WHERE TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) = ?
        """
        params = [valor_busca, valor_busca, limit]
    elif tipo == "interrupcao":
        ocorrencias_sql = """
            SELECT DISTINCT NUM_OCORRENCIA_ADMS
            FROM gold_interrupcao_tratada
            WHERE TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) = ?
            UNION
            SELECT DISTINCT NUM_OCORRENCIA_ADMS
            FROM gold_reclamacao_uc_vinculada
            WHERE TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) = ?
        """
        params = [valor_busca, valor_busca, limit]
    else:
        ocorrencias_sql = """
            SELECT DISTINCT NUM_OCORRENCIA_ADMS
            FROM gold_apuracao_uc
            WHERE TRIM(CAST(NUM_UC_UCI AS VARCHAR)) = ?
            UNION
            SELECT DISTINCT NUM_OCORRENCIA_ADMS
            FROM gold_interrupcao_tratada
            WHERE TRIM(CAST(NUM_UC_UCI AS VARCHAR)) = ?
            UNION
            SELECT DISTINCT NUM_OCORRENCIA_ADMS
            FROM gold_reclamacao_uc_vinculada
            WHERE TRIM(CAST(UC AS VARCHAR)) = ?
        """
        params = [valor_busca, valor_busca, valor_busca, limit]

    with duckdb.connect(str(db_path), read_only=True) as con:
        return _fetch_rows(
            con,
            f"""
            WITH ocorrencias AS (
                SELECT DISTINCT TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS
                FROM ({ocorrencias_sql}) origem
                WHERE NUM_OCORRENCIA_ADMS IS NOT NULL
                  AND TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) <> ''
            ),
            interrupcoes AS (
                SELECT
                    NUM_OCORRENCIA_ADMS,
                    COUNT(DISTINCT NUM_SEQ_INTRP) AS QTD_INTERRUPCOES,
                    COUNT(DISTINCT NUM_UC_UCI) AS QTD_UCS_INTERRUPCAO,
                    MIN(DATA_HORA_INIC_INTRP) AS PRIMEIRO_INICIO,
                    MAX(DATA_HORA_FIM_INTRP) AS ULTIMO_FIM,
                    STRING_AGG(DISTINCT TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)), ', ' ORDER BY TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR))) AS INTERRUPCOES,
                    STRING_AGG(DISTINCT TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) || '/' || TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)), ', ') AS PARES_COMPONENTE_CAUSA
                FROM gold_interrupcao_tratada
                WHERE NUM_OCORRENCIA_ADMS IN (SELECT NUM_OCORRENCIA_ADMS FROM ocorrencias)
                GROUP BY NUM_OCORRENCIA_ADMS
            ),
            apuracao AS (
                SELECT
                    NUM_OCORRENCIA_ADMS,
                    COUNT(*) AS QTD_LINHAS_APURACAO,
                    COUNT(DISTINCT NUM_UC_UCI) AS QTD_UCS_APURACAO,
                    SUM(COALESCE(CHI_BRUTO, 0)) AS CHI_BRUTO,
                    SUM(COALESCE(CI_BRUTO, 0)) AS CI_BRUTO,
                    SUM(COALESCE(CHI_LIQUIDO, 0)) AS CHI_LIQUIDO,
                    SUM(COALESCE(CI_LIQUIDO, 0)) AS CI_LIQUIDO
                FROM gold_apuracao_uc
                WHERE NUM_OCORRENCIA_ADMS IN (SELECT NUM_OCORRENCIA_ADMS FROM ocorrencias)
                GROUP BY NUM_OCORRENCIA_ADMS
            ),
            reclamacoes AS (
                SELECT
                    NUM_OCORRENCIA_ADMS,
                    COUNT(*) AS QTD_RECLAMACOES_VINCULADAS,
                    COUNT(DISTINCT UC) AS QTD_UCS_RECLAMANTES,
                    MAX(SCORE_VINCULO_RECLAMACAO) AS MAX_SCORE_RECLAMACAO,
                    STRING_AGG(DISTINCT TIPO_RECLAMACAO_PROVAVEL, ', ') AS TIPOS_RECLAMACAO,
                    STRING_AGG(DISTINCT CAUSA_PROVAVEL_RECLAMACAO, ', ') AS CAUSAS_RECLAMACAO
                FROM gold_reclamacao_uc_vinculada
                WHERE NUM_OCORRENCIA_ADMS IN (SELECT NUM_OCORRENCIA_ADMS FROM ocorrencias)
                GROUP BY NUM_OCORRENCIA_ADMS
            )
            SELECT
                o.NUM_OCORRENCIA_ADMS,
                COALESCE(i.QTD_INTERRUPCOES, 0) AS QTD_INTERRUPCOES,
                COALESCE(i.QTD_UCS_INTERRUPCAO, 0) AS QTD_UCS_INTERRUPCAO,
                i.PRIMEIRO_INICIO,
                i.ULTIMO_FIM,
                i.INTERRUPCOES,
                i.PARES_COMPONENTE_CAUSA,
                COALESCE(a.QTD_LINHAS_APURACAO, 0) AS QTD_LINHAS_APURACAO,
                COALESCE(a.QTD_UCS_APURACAO, 0) AS QTD_UCS_APURACAO,
                COALESCE(a.CHI_BRUTO, 0) AS CHI_BRUTO,
                COALESCE(a.CI_BRUTO, 0) AS CI_BRUTO,
                COALESCE(a.CHI_LIQUIDO, 0) AS CHI_LIQUIDO,
                COALESCE(a.CI_LIQUIDO, 0) AS CI_LIQUIDO,
                COALESCE(r.QTD_RECLAMACOES_VINCULADAS, gr.QTD_RECLAMACOES, 0) AS QTD_RECLAMACOES,
                COALESCE(r.QTD_UCS_RECLAMANTES, gr.QTD_UCS_RECLAMANTES, 0) AS QTD_UCS_RECLAMANTES,
                COALESCE(r.MAX_SCORE_RECLAMACAO, gr.MAX_SCORE_VINCULO_RECLAMACAO) AS MAX_SCORE_RECLAMACAO,
                COALESCE(r.TIPOS_RECLAMACAO, gr.TIPOS_RECLAMACAO_PROVAVEIS) AS TIPOS_RECLAMACAO,
                COALESCE(r.CAUSAS_RECLAMACAO, gr.CAUSAS_PROVAVEIS_RECLAMACAO) AS CAUSAS_RECLAMACAO,
                gr.GRUPOS_COMPONENTE_IQS,
                gr.GRUPOS_CAUSA_IQS
            FROM ocorrencias o
            LEFT JOIN gold_reclamacao_ocorrencia_resumo gr
              ON o.NUM_OCORRENCIA_ADMS = gr.NUM_OCORRENCIA_ADMS
            LEFT JOIN interrupcoes i
              ON o.NUM_OCORRENCIA_ADMS = i.NUM_OCORRENCIA_ADMS
            LEFT JOIN apuracao a
              ON o.NUM_OCORRENCIA_ADMS = a.NUM_OCORRENCIA_ADMS
            LEFT JOIN reclamacoes r
              ON o.NUM_OCORRENCIA_ADMS = r.NUM_OCORRENCIA_ADMS
            ORDER BY COALESCE(r.MAX_SCORE_RECLAMACAO, gr.MAX_SCORE_VINCULO_RECLAMACAO, 0) DESC,
                     COALESCE(a.CHI_LIQUIDO, 0) DESC,
                     o.NUM_OCORRENCIA_ADMS
            LIMIT ?
            """,
            params,
        )


@router.get("/ocorrencias/{num_ocorrencia_adms}")
def detalhe_ocorrencia(
    num_ocorrencia_adms: str,
    anomes: str = "202606",
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA")),
) -> dict[str, object]:
    db_path = _processed_path(anomes)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"DuckDB processado não encontrado: {db_path}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        ocorrencia = _fetch_rows(
            con,
            """
            SELECT *
            FROM gold_reclamacao_ocorrencia_resumo
            WHERE NUM_OCORRENCIA_ADMS = ?
            LIMIT 1
            """,
            [num_ocorrencia_adms],
        )
        interrupcoes = _fetch_rows(
            con,
            """
            WITH base AS (
                SELECT *
                FROM gold_interrupcao_tratada
                WHERE NUM_OCORRENCIA_ADMS = ?
            ),
            contagem AS (
                SELECT
                    NUM_SEQ_INTRP,
                    COUNT(*) AS QTD_LINHAS_BASE,
                    COUNT(DISTINCT NUM_UC_UCI) AS QTD_UCS_APURADAS
                FROM base
                GROUP BY NUM_SEQ_INTRP
            ),
            escolhida AS (
                SELECT
                    NUM_OCORRENCIA_ADMS,
                    NUM_SEQ_INTRP,
                    ALIM_INTRP,
                    NUM_OPER_CHV_INTRP,
                    TIPO_CHV_INTRP,
                    ESTADO_INTRP,
                    VALID_POS_OPERACAO,
                    DATA_HORA_INIC_INTRP,
                    DATA_HORA_FIM_INTRP,
                    COD_COMP_INTRP,
                    COD_CAUSA_INTRP,
                    COD_TIPO_INTRP,
                    COD_GRUPO_COMP_INTRP,
                    COD_COND_CLIMA_INTRP,
                    DESC_INTRP,
                    ROW_NUMBER() OVER (
                        PARTITION BY NUM_SEQ_INTRP
                        ORDER BY DATA_HORA_INIC_INTRP NULLS LAST, DATA_HORA_FIM_INTRP NULLS LAST
                    ) AS rn
                FROM base
            )
            SELECT
                e.NUM_OCORRENCIA_ADMS,
                e.NUM_SEQ_INTRP,
                e.ALIM_INTRP,
                e.NUM_OPER_CHV_INTRP,
                e.TIPO_CHV_INTRP,
                e.ESTADO_INTRP,
                e.VALID_POS_OPERACAO,
                e.DATA_HORA_INIC_INTRP,
                e.DATA_HORA_FIM_INTRP,
                e.COD_COMP_INTRP,
                e.COD_CAUSA_INTRP,
                e.COD_TIPO_INTRP,
                e.COD_GRUPO_COMP_INTRP,
                e.COD_COND_CLIMA_INTRP,
                e.DESC_INTRP,
                c.QTD_UCS_APURADAS,
                c.QTD_LINHAS_BASE
            FROM escolhida e
            LEFT JOIN contagem c
              ON e.NUM_SEQ_INTRP = c.NUM_SEQ_INTRP
            WHERE e.rn = 1
            ORDER BY DATA_HORA_INIC_INTRP, NUM_SEQ_INTRP
            LIMIT 200
            """,
            [num_ocorrencia_adms],
        )
        intrps = sorted(
            {
                str(row.get("NUM_SEQ_INTRP")).strip()
                for row in interrupcoes
                if row.get("NUM_SEQ_INTRP") is not None and str(row.get("NUM_SEQ_INTRP")).strip()
            }
        )
        servicos: list[dict[str, object]] = []
        raw_services_path = _raw_services_path(anomes)
        if raw_services_path.exists() and intrps:
            placeholders = ", ".join("?" for _ in intrps)
            con.execute(f"ATTACH {_sql_literal(raw_services_path)} AS serv_raw (READ_ONLY)")
            servicos = _fetch_rows(
                con,
                f"""
                SELECT
                    TRIM(CAST(s.PID_INTRP_SRVE AS VARCHAR)) AS NUM_SEQ_INTRP,
                    s.NUM_SEQ_SERV,
                    s.INDIC_EST_SERV_SRV,
                    s.NUM_ORG_EXEC_SRV,
                    s.DTHR_SOLIC_SRV,
                    s.DTHR_DESPACH_SRV,
                    s.DTHR_INIC_SRV,
                    s.DTHR_TERM_SRV,
                    s.DTHR_FECH_SRV,
                    LPAD(NULLIF(TRIM(CAST(s.COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') AS COD_CAUSA_SRVE,
                    c.DESC_CAUSA AS DESC_CAUSA_SRVE,
                    s.COD_COMP_SRVE,
                    p.DESC_COMP AS DESC_COMP_SRVE,
                    s.COD_COND_CLIMA_SRVE,
                    s.QTDE_RECLAM_SRVE
                FROM serv_raw.raw_adms_servicos s
                LEFT JOIN ref_iqs_causa c
                  ON LPAD(NULLIF(TRIM(CAST(s.COD_CAUSA_SRVE AS VARCHAR)), ''), 2, '0') = c.COD_CAUSA
                LEFT JOIN ref_iqs_componente p
                  ON TRIM(CAST(s.COD_COMP_SRVE AS VARCHAR)) = p.COD_COMP
                WHERE TRIM(CAST(s.PID_INTRP_SRVE AS VARCHAR)) IN ({placeholders})
                ORDER BY s.DTHR_SOLIC_SRV, s.NUM_SEQ_SERV
                LIMIT 200
                """,
                intrps,
            )
        apuracao_uc = _fetch_rows(
            con,
            """
            SELECT
                a.NUM_UC_UCI,
                a.DURACAO_HORA,
                a.CHI_LIQUIDO,
                a.CI_LIQUIDO,
                a.CHI_BRUTO,
                a.CI_BRUTO,
                r.CLASSE_TENSAO_PRODIST,
                r.GRUPO_TENSAO,
                r.COD_NIVEL_TENSAO_UC,
                r.COMP_TOTAL_PRODIST AS VALOR_RESSARCIMENTO
            FROM gold_apuracao_uc a
            LEFT JOIN gold_ressarcimento_prodist r
              ON TRIM(CAST(a.NUM_UC_UCI AS VARCHAR)) = TRIM(CAST(r.UC AS VARCHAR))
            WHERE a.NUM_OCORRENCIA_ADMS = ?
            ORDER BY a.CHI_LIQUIDO DESC NULLS LAST
            LIMIT 100
            """,
            [num_ocorrencia_adms],
        )
        reclamacoes = _fetch_rows(
            con,
            """
            SELECT
                ID_RECLAMACAO,
                UC,
                DTHR_RECLAMACAO,
                TIPO_RECLAMACAO_PROVAVEL,
                CAUSA_PROVAVEL_RECLAMACAO,
                NUM_OCORRENCIA_ADMS,
                NUM_SEQ_INTRP,
                SCORE_VINCULO_RECLAMACAO,
                CLASSIFICACAO_VINCULO_RECLAMACAO,
                DISTANCIA_MINUTOS,
                TEXTO_RECLAMACAO,
                TEXTO_RETORNO
            FROM gold_reclamacao_uc_vinculada
            WHERE NUM_OCORRENCIA_ADMS = ?
            ORDER BY SCORE_VINCULO_RECLAMACAO DESC NULLS LAST, DTHR_RECLAMACAO
            LIMIT 100
            """,
            [num_ocorrencia_adms],
        )

    return {
        "anomes": anomes,
        "num_ocorrencia_adms": num_ocorrencia_adms,
        "ocorrencia": ocorrencia[0] if ocorrencia else None,
        "interrupcoes": interrupcoes,
        "servicos": servicos,
        "apuracao_uc": apuracao_uc,
        "reclamacoes": reclamacoes,
    }

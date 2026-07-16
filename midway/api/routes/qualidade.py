from __future__ import annotations

from pathlib import Path

import duckdb
from fastapi import APIRouter, Depends, HTTPException, Query

from midway.api.security import AuthUser, require_profiles
from midway.api.serialization import api_rows
from midway.qualidade.analise_tecnica_cache import source_sql

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


def _duckdb_busy_message(exc: Exception) -> str:
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    useful = [
        line
        for line in lines
        if "IO Error" in line
        or "Cannot open file" in line
        or "already open" in line
        or "sendo usado" in line
        or "PID " in line
    ]
    message = " ".join(useful or lines[:2])
    return message or str(exc)


def _connect_processed_readonly(db_path: Path) -> duckdb.DuckDBPyConnection:
    try:
        return duckdb.connect(str(db_path), read_only=True)
    except (duckdb.Error, OSError) as exc:
        raise HTTPException(
            status_code=423,
            detail=(
                "DuckDB processado está ocupado por outro processo. "
                f"Feche API/job antigo, Streamlit ou notebook usando o arquivo e tente novamente. Detalhe: {_duckdb_busy_message(exc)}"
            ),
        ) from None


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return (
        con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE lower(table_name) = lower(?)
            """,
            [table_name],
        ).fetchone()[0]
        > 0
    )


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

    with _connect_processed_readonly(db_path) as con:
        rows = _fetch_rows(
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
        ocorrencias = [str(row.get("NUM_OCORRENCIA_ADMS") or "").strip() for row in rows]
        ocorrencias = [item for item in ocorrencias if item]
        detalhes_por_ocorrencia: dict[str, list[dict[str, object]]] = {item: [] for item in ocorrencias}

        if ocorrencias:
            placeholders = ", ".join(["?"] * len(ocorrencias))
            detalhes = _fetch_rows(
                con,
                f"""
                SELECT
                    TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) AS NUM_OCORRENCIA_ADMS,
                    TRIM(CAST(NUM_SEQ_INTRP AS VARCHAR)) AS NUM_SEQ_INTRP,
                    MIN(DATA_HORA_INIC_INTRP) AS INICIO,
                    MAX(DATA_HORA_FIM_INTRP) AS FIM,
                    COUNT(DISTINCT NUM_UC_UCI) AS QTD_UCS,
                    STRING_AGG(
                        DISTINCT TRIM(CAST(COD_COMP_INTRP AS VARCHAR)) || '/' || TRIM(CAST(COD_CAUSA_INTRP AS VARCHAR)),
                        ', '
                    ) AS PARES_COMPONENTE_CAUSA,
                    ROUND(
                        GREATEST(
                            DATE_DIFF(
                                'second',
                                MIN(DATA_HORA_INIC_INTRP),
                                COALESCE(MAX(DATA_HORA_FIM_INTRP), MIN(DATA_HORA_INIC_INTRP))
                            ) / 3600.0,
                            0
                        ),
                        4
                    ) AS DURACAO_HORAS
                FROM gold_interrupcao_tratada
                WHERE TRIM(CAST(NUM_OCORRENCIA_ADMS AS VARCHAR)) IN ({placeholders})
                GROUP BY 1, 2
                ORDER BY 1, INICIO, NUM_SEQ_INTRP
                """,
                ocorrencias,
            )
            for detalhe in detalhes:
                ocorrencia = str(detalhe.get("NUM_OCORRENCIA_ADMS") or "").strip()
                detalhes_por_ocorrencia.setdefault(ocorrencia, []).append(detalhe)

        for row in rows:
            ocorrencia = str(row.get("NUM_OCORRENCIA_ADMS") or "").strip()
            row["INTERRUPCOES_DETALHE"] = detalhes_por_ocorrencia.get(ocorrencia, [])

        return rows


@router.get("/analise-tecnica/opcoes")
def opcoes_analise_tecnica(
    anomes: str = "202606",
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA")),
) -> dict[str, list[dict[str, object]]]:
    db_path = _processed_path(anomes)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"DuckDB processado não encontrado: {db_path}")

    with _connect_processed_readonly(db_path) as con:
        if not _table_exists(con, "gold_iqs_referencia_componente_causa"):
            raise HTTPException(status_code=404, detail="Referência IQS de grupo/componente/causa não encontrada.")

        grupos = _fetch_rows(
            con,
            """
            SELECT
                NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') AS codigo,
                NULLIF(TRIM(CAST(DESC_GRUPO_GCR AS VARCHAR)), '') AS descricao
            FROM gold_iqs_referencia_componente_causa
            WHERE NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1, 2
            ORDER BY 1
            """,
            [],
        )
        componentes = _fetch_rows(
            con,
            """
            SELECT
                NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') AS codigo,
                NULLIF(TRIM(CAST(DESC_COMP AS VARCHAR)), '') AS descricao,
                NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') AS grupo_codigo,
                NULLIF(TRIM(CAST(DESC_GRUPO_GCR AS VARCHAR)), '') AS grupo_descricao
            FROM gold_iqs_referencia_componente_causa
            WHERE NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1, 2, 3, 4
            ORDER BY 3, 1
            """,
            [],
        )
        causas = _fetch_rows(
            con,
            """
            SELECT
                LPAD(NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), ''), 2, '0') AS codigo,
                NULLIF(TRIM(CAST(DESC_CAUSA AS VARCHAR)), '') AS descricao,
                NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') AS componente_codigo,
                NULLIF(TRIM(CAST(DESC_COMP AS VARCHAR)), '') AS componente_descricao,
                NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') AS grupo_codigo
            FROM gold_iqs_referencia_componente_causa
            WHERE NULLIF(TRIM(CAST(COD_CAUSA AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_COMP AS VARCHAR)), '') IS NOT NULL
              AND NULLIF(TRIM(CAST(COD_GRUPO_GCR AS VARCHAR)), '') IS NOT NULL
            GROUP BY 1, 2, 3, 4, 5
            ORDER BY 5, 3, 1
            """,
            [],
        )

    return {"grupos": grupos, "componentes": componentes, "causas": causas}


@router.get("/analise-tecnica")
def analise_tecnica_impacto(
    anomes: str = "202606",
    min_chi: float | None = Query(None, ge=0),
    min_ci: float | None = Query(None, ge=0),
    min_ressarcimento: float | None = Query(None, ge=0),
    componente: str | None = None,
    causa: str | None = None,
    grupo: str | None = None,
    problema: str = Query(
        "todos",
        pattern="^(todos|impacto|9282|violacao_componente_causa|duracao_suspeita|ressarcimento)$",
    ),
    duracao_suspeita_min: float = Query(24, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA")),
) -> dict[str, object]:
    db_path = _processed_path(anomes)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"DuckDB processado não encontrado: {db_path}")

    filters: list[str] = []
    params: list[object] = []
    if min_chi is not None:
        filters.append("CHI_LIQUIDO >= ?")
        params.append(min_chi)
    if min_ci is not None:
        filters.append("CI_LIQUIDO >= ?")
        params.append(min_ci)
    if min_ressarcimento is not None:
        filters.append("RESSARCIMENTO_ESTIMADO >= ?")
        params.append(min_ressarcimento)
    if componente and componente.strip():
        filters.append("COD_COMP_PRINCIPAL = ?")
        params.append(componente.strip())
    if causa and causa.strip():
        filters.append("COD_CAUSA_PRINCIPAL = ?")
        params.append(causa.strip().zfill(2))
    if grupo and grupo.strip():
        filters.append("COD_GRUPO_PRINCIPAL = ?")
        params.append(grupo.strip())
    if problema == "9282":
        filters.append("TEM_9282 = 1")
    elif problema == "violacao_componente_causa":
        filters.append("QTD_VIOLACAO_COMP_CAUSA > 0")
    elif problema == "duracao_suspeita":
        filters.append("DURACAO_MAX_HORA >= ?")
        params.append(duracao_suspeita_min)
    elif problema == "ressarcimento":
        filters.append("RESSARCIMENTO_ESTIMADO > 0")

    where_sql = "WHERE " + " AND ".join(filters) if filters else ""
    ranking_params = [duracao_suspeita_min, *params, limit]
    resumo_params = [duracao_suspeita_min, *params, duracao_suspeita_min]

    score_sql = """
        LEAST(LN(1 + COALESCE(CHI_LIQUIDO, 0)) * 8, 60)
      + LEAST(LN(1 + COALESCE(CI_LIQUIDO, 0)) * 6, 35)
      + LEAST(LN(1 + COALESCE(RESSARCIMENTO_ESTIMADO, 0)) * 5, 35)
      + CASE WHEN COALESCE(QTD_VIOLACAO_COMP_CAUSA, 0) > 0 THEN 35 ELSE 0 END
      + CASE WHEN COALESCE(TEM_9282, 0) = 1 THEN 15 ELSE 0 END
      + CASE WHEN DURACAO_MAX_HORA >= ? THEN 20 ELSE 0 END
      + LEAST(COALESCE(MAX_SCORE_RECLAMACAO, 0) / 5, 20)
    """

    with _connect_processed_readonly(db_path) as con:
        origem_sql, usando_cache = source_sql(con)
        cte_sql = f"""
            WITH origem AS (
                {origem_sql}
            ),
            base AS (
                SELECT
                    *,
                    ({score_sql}) AS IMPACTO_SCORE
                FROM origem
            ),
            filtrado AS (
                SELECT *
                FROM base
                {where_sql}
            )
        """
        rows = _fetch_rows(
            con,
            f"""
            {cte_sql}
            SELECT *
            FROM filtrado
            ORDER BY IMPACTO_SCORE DESC, CHI_LIQUIDO DESC, CI_LIQUIDO DESC, NUM_OCORRENCIA_ADMS
            LIMIT ?
            """,
            ranking_params,
        )
        resumo_rows = _fetch_rows(
            con,
            f"""
            {cte_sql}
            SELECT
                COUNT(*) AS QTD_OCORRENCIAS,
                SUM(COALESCE(CHI_LIQUIDO, 0)) AS CHI_LIQUIDO_TOTAL,
                SUM(COALESCE(CI_LIQUIDO, 0)) AS CI_LIQUIDO_TOTAL,
                SUM(COALESCE(RESSARCIMENTO_ESTIMADO, 0)) AS RESSARCIMENTO_ESTIMADO_TOTAL,
                SUM(CASE WHEN QTD_VIOLACAO_COMP_CAUSA > 0 THEN 1 ELSE 0 END) AS QTD_OCORRENCIAS_COM_VIOLACAO,
                SUM(CASE WHEN TEM_9282 = 1 THEN 1 ELSE 0 END) AS QTD_OCORRENCIAS_9282,
                SUM(CASE WHEN DURACAO_MAX_HORA >= ? THEN 1 ELSE 0 END) AS QTD_DURACAO_SUSPEITA,
                MAX(IMPACTO_SCORE) AS MAIOR_IMPACTO_SCORE
            FROM filtrado
            """,
            resumo_params,
        )

    return {
        "anomes": anomes,
        "fonte": "cache" if usando_cache else "calculo_ao_vivo",
        "filtros": {
            "min_chi": min_chi,
            "min_ci": min_ci,
            "min_ressarcimento": min_ressarcimento,
            "componente": componente,
            "causa": causa,
            "grupo": grupo,
            "problema": problema,
            "duracao_suspeita_min": duracao_suspeita_min,
            "limit": limit,
        },
        "resumo": resumo_rows[0] if resumo_rows else {},
        "itens": rows,
    }


@router.get("/ocorrencias/{num_ocorrencia_adms}")
def detalhe_ocorrencia(
    num_ocorrencia_adms: str,
    anomes: str = "202606",
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA")),
) -> dict[str, object]:
    db_path = _processed_path(anomes)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"DuckDB processado não encontrado: {db_path}")

    with _connect_processed_readonly(db_path) as con:
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

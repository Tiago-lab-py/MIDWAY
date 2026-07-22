from __future__ import annotations

from pathlib import Path
from typing import Annotated

import duckdb
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from midway.api.security import AuthUser, require_profiles
from midway.api.serialization import api_row, api_rows
from midway.db.postgres import create_postgres_engine, get_config

router = APIRouter(prefix="/api/executivo/9282", tags=["executivo-9282"])


class Autorizar9282Request(BaseModel):
    justificativa: str | None = None
    incluir_justificativas_processos: bool = False
    justificativas_processos: list[str] = []


def _schema() -> str:
    schema = get_config().schema
    if not schema.replace("_", "").isalnum():
        raise HTTPException(status_code=500, detail="Schema PostgreSQL inválido.")
    return schema


def _limit_value(limit: int) -> int:
    return max(1, min(limit, 1000))


def _processed_path(anomes: str) -> Path:
    return Path("data/processed") / f"iqs_adms_processed_{anomes}.duckdb"


def _raw_path(anomes: str) -> Path:
    return Path("data/raw") / f"iqs_adms_raw_{anomes}.duckdb"


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _api_error(error: Exception) -> HTTPException:
    if isinstance(error, HTTPException):
        return error
    return HTTPException(status_code=503, detail=f"Falha ao consultar PostgreSQL: {error}")


@router.get("/painel")
def painel_9282(anomes: str | None = None) -> list[dict[str, object]]:
    try:
        schema = _schema()
        sql = f"SELECT * FROM {schema}.vw_midway_9282_painel"
        params: dict[str, object] = {}
        if anomes:
            sql += " WHERE anomes = :anomes"
            params["anomes"] = anomes
        sql += " ORDER BY anomes DESC"

        engine = create_postgres_engine()
        with engine.connect() as con:
            rows = con.execute(text(sql), params).mappings().all()
        return api_rows([dict(row) for row in rows])
    except Exception as error:
        raise _api_error(error) from error


@router.get("/dec-fec")
def dec_fec_tratativas(anomes: str = "202606") -> dict[str, object]:
    db_path = _processed_path(anomes)
    raw_path = _raw_path(anomes)
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"DuckDB processado não encontrado: {db_path}")
    if not raw_path.exists():
        raise HTTPException(status_code=404, detail=f"DuckDB RAW não encontrado: {raw_path}")

    with duckdb.connect(str(db_path), read_only=True) as con:
        con.execute(f"ATTACH {_sql_literal(raw_path)} AS raw_db (READ_ONLY)")
        row = con.execute(
            """
            WITH denominador AS (
                SELECT MAX(UC_FATURADA) AS total_consumidores
                FROM gold_consumidores
                WHERE REGIONAL_TOTAL = 'COPEL'
            ),
            raw_base AS (
                SELECT
                    CAST(r.PID_OCOR_INTRP_ULT_HIADMS AS VARCHAR) AS NUM_OCORRENCIA_ADMS,
                    CAST(r.NUM_SEQ_INTRP_CHVP_HIADMS AS VARCHAR) AS NUM_SEQ_INTRP,
                    CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR) AS NUM_UC_UCI,
                    CAST(r.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR) AS TIPO_PROTOC_JUSTIF_UCI,
                    DATE_DIFF(
                        'second',
                        r.DATA_HORA_INIC_INTRP_ULT_HIADMS,
                        r.DATA_HORA_FIM_INTRP_ULT_HIADMS
                    ) / 3600.0 AS DURACAO_HORA
                FROM raw_db.hiadms_raw r
                WHERE r.DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
                  AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
                  AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS >= r.DATA_HORA_INIC_INTRP_ULT_HIADMS
                  AND TRIM(CAST(r.ESTADO_INTRP_ULT_HIADMS AS VARCHAR)) = '4'
                  AND DATE_DIFF(
                        'second',
                        r.DATA_HORA_INIC_INTRP_ULT_HIADMS,
                        r.DATA_HORA_FIM_INTRP_ULT_HIADMS
                    ) >= 180
                  AND EXISTS (
                      SELECT 1
                      FROM gold_uc_fatura u
                      WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR))
                        AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                  )
            ),
            pos AS (
                SELECT
                    SUM(COALESCE(CI_BRUTO, 0)) AS ci_bruto,
                    SUM(COALESCE(CHI_BRUTO, 0)) AS chi_bruto,
                    SUM(COALESCE(CI_LIQUIDO, 0)) AS ci_liquido,
                    SUM(COALESCE(CHI_LIQUIDO, 0)) AS chi_liquido,
                    COUNT(*) AS linhas_bdo
                FROM gold_apuracao_previa
            ),
            raw_agg AS (
                SELECT
                    COUNT(*) AS ci_bruto,
                    SUM(DURACAO_HORA) AS chi_bruto,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN DURACAO_HORA ELSE 0 END) AS chi_liquido,
                    COUNT(*) AS linhas_raw,
                    COUNT(DISTINCT NUM_OCORRENCIA_ADMS) AS ocorrencias_raw,
                    COUNT(DISTINCT NUM_SEQ_INTRP) AS interrupcoes_raw,
                    COUNT(DISTINCT NUM_UC_UCI) AS ucs_raw
                FROM raw_base
            )
            SELECT
                r.chi_bruto / NULLIF(d.total_consumidores, 0) AS dec_bruto_antes,
                r.ci_bruto / NULLIF(d.total_consumidores, 0) AS fec_bruto_antes,
                p.chi_bruto / NULLIF(d.total_consumidores, 0) AS dec_bruto_depois,
                p.ci_bruto / NULLIF(d.total_consumidores, 0) AS fec_bruto_depois,
                r.chi_liquido / NULLIF(d.total_consumidores, 0) AS dec_liquido_antes,
                r.ci_liquido / NULLIF(d.total_consumidores, 0) AS fec_liquido_antes,
                p.chi_liquido / NULLIF(d.total_consumidores, 0) AS dec_liquido_depois,
                p.ci_liquido / NULLIF(d.total_consumidores, 0) AS fec_liquido_depois,
                r.chi_bruto AS chi_bruto_antes,
                r.ci_bruto AS ci_bruto_antes,
                p.chi_bruto AS chi_bruto_depois,
                p.ci_bruto AS ci_bruto_depois,
                r.chi_liquido AS chi_liquido_antes,
                r.ci_liquido AS ci_liquido_antes,
                p.chi_liquido AS chi_liquido_depois,
                p.ci_liquido AS ci_liquido_depois,
                r.ocorrencias_raw,
                r.interrupcoes_raw,
                r.ucs_raw,
                r.linhas_raw,
                p.linhas_bdo,
                d.total_consumidores
            FROM raw_agg r
            CROSS JOIN pos p
            CROSS JOIN denominador d
            """
        ).fetchone()
        tratamentos = con.execute(
            """
            WITH denominador AS (
                SELECT MAX(UC_FATURADA) AS total_consumidores
                FROM gold_consumidores
                WHERE REGIONAL_TOTAL = 'COPEL'
            ),
            impacto_total AS (
                SELECT
                    'Sobreposição total UC' AS tratamento,
                    COUNT(*) AS ci_bruto_ganho,
                    SUM(DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0) AS chi_bruto_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                        THEN DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0 ELSE 0 END) AS chi_liquido_ganho
                FROM export_sobreposicao_total_uc e
                WHERE TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                  AND DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) >= 180
                  AND EXISTS (
                      SELECT 1 FROM gold_uc_fatura u
                      WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(e.NUM_UC_UCI AS VARCHAR))
                        AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                  )
            ),
            impacto_parcial AS (
                SELECT
                    'Sobreposição parcial UC' AS tratamento,
                    0 AS ci_bruto_ganho,
                    SUM(GREATEST(
                        DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0
                        - DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0,
                        0
                    )) AS chi_bruto_ganho,
                    0 AS ci_liquido_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN GREATEST(
                        DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0
                        - DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0,
                        0
                    ) ELSE 0 END) AS chi_liquido_ganho
                FROM adms_iqs_alterados a
                WHERE ACAO_AJUSTE_PARCIAL = 'AJUSTAR_SOBREPOSICAO_PARCIAL_UC'
                  AND TRY_CAST(DTHR_INICIO_INTRP_UC_ORIG AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                  AND EXISTS (
                      SELECT 1 FROM gold_uc_fatura u
                      WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(a.NUM_UC_UCI AS VARCHAR))
                        AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                  )
            ),
            impacto_sem_uc AS (
                SELECT
                    'Interrupção sem UC remanescente' AS tratamento,
                    COUNT(*) AS ci_bruto_ganho,
                    SUM(DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0) AS chi_bruto_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido_ganho,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0'
                        THEN DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) / 3600.0 ELSE 0 END) AS chi_liquido_ganho
                FROM adms_iqs_interrupcao_sem_uc_export e
                WHERE TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) IS NOT NULL
                  AND TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP) >= TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP)
                  AND DATE_DIFF('second', TRY_CAST(DTHR_INICIO_INTRP_UC AS TIMESTAMP), TRY_CAST(DATA_HORA_FIM_INTRP AS TIMESTAMP)) >= 180
                  AND EXISTS (
                      SELECT 1 FROM gold_uc_fatura u
                      WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(e.NUM_UC_UCI AS VARCHAR))
                        AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                  )
            ),
            impactos AS (
                SELECT * FROM impacto_total
                UNION ALL SELECT * FROM impacto_parcial
                UNION ALL SELECT * FROM impacto_sem_uc
            )
            SELECT
                tratamento,
                COALESCE(chi_bruto_ganho, 0) / NULLIF(total_consumidores, 0) AS dec_bruto_ganho,
                COALESCE(ci_bruto_ganho, 0) / NULLIF(total_consumidores, 0) AS fec_bruto_ganho,
                COALESCE(chi_liquido_ganho, 0) / NULLIF(total_consumidores, 0) AS dec_liquido_ganho,
                COALESCE(ci_liquido_ganho, 0) / NULLIF(total_consumidores, 0) AS fec_liquido_ganho,
                COALESCE(chi_bruto_ganho, 0) AS chi_bruto_ganho,
                COALESCE(ci_bruto_ganho, 0) AS ci_bruto_ganho,
                COALESCE(chi_liquido_ganho, 0) AS chi_liquido_ganho,
                COALESCE(ci_liquido_ganho, 0) AS ci_liquido_ganho
            FROM impactos
            CROSS JOIN denominador
            ORDER BY dec_bruto_ganho DESC
            """
        ).fetchdf().to_dict(orient="records")
        filtros_apuracao = con.execute(
            """
            WITH denominador AS (
                SELECT MAX(UC_FATURADA) AS total_consumidores
                FROM gold_consumidores
                WHERE REGIONAL_TOTAL = 'COPEL'
            ),
            raw_base AS (
                SELECT
                    DATE_DIFF(
                        'second',
                        r.DATA_HORA_INIC_INTRP_ULT_HIADMS,
                        r.DATA_HORA_FIM_INTRP_ULT_HIADMS
                    ) / 3600.0 AS DURACAO_HORA,
                    CAST(r.TIPO_PROTOC_JUSTIF_UCI_ULT_HIADMS AS VARCHAR) AS TIPO_PROTOC_JUSTIF_UCI,
                    EXISTS (
                        SELECT 1
                        FROM gold_uc_fatura u
                        WHERE TRIM(CAST(u.UC AS VARCHAR)) = TRIM(CAST(r.NUM_UC_UCI_CHVP_HIADMS AS VARCHAR))
                          AND TRIM(CAST(u.FATURADO AS VARCHAR)) = 'S'
                    ) AS FATURADO,
                    r.NUM_INTRP_INIC_MANOBRA_UCI_ULT_HIADMS AS NUM_INTRP_INIC_MANOBRA_UCI,
                    r.NUM_MOTIVO_TRAT_DIF_UCI_ULT_HIADMS AS NUM_MOTIVO_TRAT_DIF_UCI
                FROM raw_db.hiadms_raw r
                WHERE r.DATA_HORA_INIC_INTRP_ULT_HIADMS IS NOT NULL
                  AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS IS NOT NULL
                  AND r.DATA_HORA_FIM_INTRP_ULT_HIADMS >= r.DATA_HORA_INIC_INTRP_ULT_HIADMS
                  AND TRIM(CAST(r.ESTADO_INTRP_ULT_HIADMS AS VARCHAR)) = '4'
                  AND DATE_DIFF(
                        'second',
                        r.DATA_HORA_INIC_INTRP_ULT_HIADMS,
                        r.DATA_HORA_FIM_INTRP_ULT_HIADMS
                    ) >= 180
            ),
            classificados AS (
                SELECT
                    CASE
                        WHEN NOT FATURADO THEN 'Não faturados (fora DEC/FEC oficial)'
                        WHEN NUM_INTRP_INIC_MANOBRA_UCI IS NOT NULL
                         AND NUM_MOTIVO_TRAT_DIF_UCI IS NOT NULL
                            THEN 'Faturados com manobra + motivo'
                        WHEN NUM_INTRP_INIC_MANOBRA_UCI IS NOT NULL
                            THEN 'Faturados com manobra/remanejamento'
                        WHEN NUM_MOTIVO_TRAT_DIF_UCI IS NOT NULL
                            THEN 'Faturados com motivo tratamento diferenciado'
                        ELSE 'Faturados sem filtro adicional'
                    END AS tratamento,
                    CASE
                        WHEN NOT FATURADO THEN 'Fora do DEC/FEC oficial'
                        ELSE 'Demais filtros RAW'
                    END AS grupo,
                    DURACAO_HORA,
                    TIPO_PROTOC_JUSTIF_UCI
                FROM raw_base
            ),
            agregados AS (
                SELECT
                    tratamento,
                    grupo,
                    COUNT(*) AS ci_bruto_referencia,
                    SUM(DURACAO_HORA) AS chi_bruto_referencia,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN 1 ELSE 0 END) AS ci_liquido_referencia,
                    SUM(CASE WHEN TRIM(CAST(TIPO_PROTOC_JUSTIF_UCI AS VARCHAR)) = '0' THEN DURACAO_HORA ELSE 0 END) AS chi_liquido_referencia
                FROM classificados
                WHERE tratamento <> 'Faturados sem filtro adicional'
                GROUP BY tratamento, grupo
            )
            SELECT
                tratamento,
                grupo,
                COALESCE(chi_bruto_referencia, 0) / NULLIF(total_consumidores, 0) AS dec_bruto_referencia,
                COALESCE(ci_bruto_referencia, 0) / NULLIF(total_consumidores, 0) AS fec_bruto_referencia,
                COALESCE(chi_liquido_referencia, 0) / NULLIF(total_consumidores, 0) AS dec_liquido_referencia,
                COALESCE(ci_liquido_referencia, 0) / NULLIF(total_consumidores, 0) AS fec_liquido_referencia,
                COALESCE(chi_bruto_referencia, 0) AS chi_bruto_referencia,
                COALESCE(ci_bruto_referencia, 0) AS ci_bruto_referencia,
                COALESCE(chi_liquido_referencia, 0) AS chi_liquido_referencia,
                COALESCE(ci_liquido_referencia, 0) AS ci_liquido_referencia
            FROM agregados
            CROSS JOIN denominador
            ORDER BY
                CASE tratamento
                    WHEN 'Não faturados (fora DEC/FEC oficial)' THEN 1
                    WHEN 'Faturados com manobra/remanejamento' THEN 2
                    WHEN 'Faturados com motivo tratamento diferenciado' THEN 3
                    WHEN 'Faturados com manobra + motivo' THEN 4
                    ELSE 9
                END
            """
        ).fetchdf().to_dict(orient="records")

    keys = [
        "dec_bruto_antes",
        "fec_bruto_antes",
        "dec_bruto_depois",
        "fec_bruto_depois",
        "dec_liquido_antes",
        "fec_liquido_antes",
        "dec_liquido_depois",
        "fec_liquido_depois",
        "chi_bruto_antes",
        "ci_bruto_antes",
        "chi_bruto_depois",
        "ci_bruto_depois",
        "chi_liquido_antes",
        "ci_liquido_antes",
        "chi_liquido_depois",
        "ci_liquido_depois",
        "ocorrencias_raw",
        "interrupcoes_raw",
        "ucs_raw",
        "linhas_raw",
        "linhas_bdo",
        "total_consumidores",
    ]
    result = dict(zip(keys, row, strict=True))
    result["anomes"] = anomes
    result["metodo"] = "raw_vs_apuracao_previa"
    result["fonte"] = "raw_db.hiadms_raw vs gold_apuracao_previa"
    result["premissa"] = (
        "Antes usa RAW hiadms_raw com ESTADO_INTRP=4, duração >= 3 min e UC faturada. "
        "Depois usa gold_apuracao_previa após correções de sobreposição e demais tratativas. "
        "Bruto usa todos os protocolos; líquido usa TIPO_PROTOC_JUSTIF_UCI = 0."
    )
    for indicador in ("dec_bruto", "fec_bruto", "dec_liquido", "fec_liquido", "chi_bruto", "ci_bruto", "chi_liquido", "ci_liquido"):
        antes = float(result.get(f"{indicador}_antes") or 0)
        depois = float(result.get(f"{indicador}_depois") or 0)
        result[f"{indicador}_ganho"] = antes - depois
        result[f"{indicador}_ganho_pct"] = (antes - depois) / antes * 100 if antes else 0

    result["dec_antes"] = result["dec_bruto_antes"]
    result["dec_depois"] = result["dec_bruto_depois"]
    result["dec_ganho"] = result["dec_bruto_ganho"]
    result["dec_ganho_pct"] = result["dec_bruto_ganho_pct"]
    result["fec_antes"] = result["fec_bruto_antes"]
    result["fec_depois"] = result["fec_bruto_depois"]
    result["fec_ganho"] = result["fec_bruto_ganho"]
    result["fec_ganho_pct"] = result["fec_bruto_ganho_pct"]

    colunas_ganho = (
        "dec_bruto_ganho",
        "fec_bruto_ganho",
        "dec_liquido_ganho",
        "fec_liquido_ganho",
        "chi_bruto_ganho",
        "ci_bruto_ganho",
        "chi_liquido_ganho",
        "ci_liquido_ganho",
    )
    tratamentos_fechados = [dict(item) for item in tratamentos]
    soma_identificada = {
        coluna: sum(float(item.get(coluna) or 0) for item in tratamentos_fechados)
        for coluna in colunas_ganho
    }
    residual = {
        "tratamento": "Demais filtros/ajustes da apuração",
        **{
            coluna: float(result.get(coluna) or 0) - soma_identificada[coluna]
            for coluna in colunas_ganho
        },
    }
    total = {
        "tratamento": "TOTAL GANHO",
        **{coluna: float(result.get(coluna) or 0) for coluna in colunas_ganho},
    }
    result["tratamentos"] = api_rows([*tratamentos_fechados, residual, total])
    result["filtros_apuracao"] = api_rows(filtros_apuracao)
    result["observacao_filtros_apuracao"] = (
        "Abertura diagnóstica do RAW com duração >= 3 min e ESTADO_INTRP=4. "
        "Não faturados ficam fora do DEC/FEC oficial; demais filtros ajudam a explicar "
        "a linha residual, mas não substituem o fechamento validado."
    )
    return api_row(result)


@router.get("/ajustes-auto")
def ajustes_auto_9282(
    anomes: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[dict[str, object]]:
    try:
        schema = _schema()
        sql = f"SELECT * FROM {schema}.vw_midway_9282_ajustes_auto"
        params: dict[str, object] = {"limit": _limit_value(limit)}
        if anomes:
            sql += " WHERE anomes = :anomes"
            params["anomes"] = anomes
        sql += " ORDER BY criado_em DESC LIMIT :limit"

        engine = create_postgres_engine()
        with engine.connect() as con:
            rows = con.execute(text(sql), params).mappings().all()
        return api_rows([dict(row) for row in rows])
    except Exception as error:
        raise _api_error(error) from error


@router.get("/fila-tecnica")
def fila_tecnica_9282(
    anomes: str | None = None,
    status: str | None = "ABERTA",
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[dict[str, object]]:
    try:
        schema = _schema()
        conditions = []
        params: dict[str, object] = {"limit": _limit_value(limit)}
        if anomes:
            conditions.append("anomes = :anomes")
            params["anomes"] = anomes
        if status:
            conditions.append("status_fila = :status")
            params["status"] = status

        sql = f"SELECT * FROM {schema}.vw_midway_9282_fila_tecnica"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY prioridade DESC, criado_em ASC LIMIT :limit"

        engine = create_postgres_engine()
        with engine.connect() as con:
            rows = con.execute(text(sql), params).mappings().all()
        return api_rows([dict(row) for row in rows])
    except Exception as error:
        raise _api_error(error) from error


@router.get("/auditoria")
def auditoria_9282(
    anomes: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[dict[str, object]]:
    try:
        schema = _schema()
        sql = f"SELECT * FROM {schema}.vw_midway_9282_auditoria"
        params: dict[str, object] = {"limit": _limit_value(limit)}
        if anomes:
            sql += " WHERE anomes = :anomes"
            params["anomes"] = anomes
        sql += " ORDER BY criado_em DESC LIMIT :limit"

        engine = create_postgres_engine()
        with engine.connect() as con:
            rows = con.execute(text(sql), params).mappings().all()
        return api_rows([dict(row) for row in rows])
    except Exception as error:
        raise _api_error(error) from error


@router.post("/autorizar")
def autorizar_9282(
    anomes: str = "202606",
    payload: Autorizar9282Request | None = Body(default=None),
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR")),
) -> dict[str, object]:
    try:
        justificativa = ""
        if payload:
            partes = []
            if payload.justificativa:
                partes.append(payload.justificativa.strip())
            if payload.incluir_justificativas_processos:
                justificativas_unicas = []
                for item in payload.justificativas_processos or []:
                    item_limpo = item.strip()
                    if item_limpo and item_limpo not in justificativas_unicas:
                        justificativas_unicas.append(item_limpo)
                if justificativas_unicas:
                    partes.append("Justificativas dos processos aceitos: " + " | ".join(justificativas_unicas))
            justificativa = "\n\n".join(partes).strip()
            
        schema = _schema()
        engine = create_postgres_engine()
        with engine.connect() as con:
            res = con.execute(
                text(f"""
                    UPDATE {schema}.propostas_tratamento
                    SET status_governanca = 'APROVADA', 
                        acao_sugerida = COALESCE(acao_sugerida, '') || CASE WHEN :justificativa != '' THEN ' | Justificativa: ' || :justificativa ELSE '' END
                    WHERE codigo_modulo = 'CORRECAO_9282' 
                      AND status_governanca = 'PENDENTE'
                """),
                {"justificativa": justificativa}
            )
            con.commit()
            linhas_afetadas = res.rowcount

        result = {
            "status": "APROVADA",
            "linhas_afetadas": linhas_afetadas,
            "anomes": anomes,
            "responsavel": user.login
        }
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return api_row(result)

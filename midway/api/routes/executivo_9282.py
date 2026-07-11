from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from midway.api.serialization import api_row, api_rows
from midway.auditoria.correcao_9282 import registrar_ajustes_automaticos_9282_postgres
from midway.db.postgres import create_postgres_engine, get_config

router = APIRouter(prefix="/api/executivo/9282", tags=["executivo-9282"])


def _schema() -> str:
    schema = get_config().schema
    if not schema.replace("_", "").isalnum():
        raise HTTPException(status_code=500, detail="Schema PostgreSQL inválido.")
    return schema


def _limit_value(limit: int) -> int:
    return max(1, min(limit, 1000))


@router.get("/painel")
def painel_9282(anomes: str | None = None) -> list[dict[str, object]]:
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


@router.get("/ajustes-auto")
def ajustes_auto_9282(
    anomes: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[dict[str, object]]:
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


@router.get("/fila-tecnica")
def fila_tecnica_9282(
    anomes: str | None = None,
    status: str | None = "ABERTA",
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[dict[str, object]]:
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


@router.get("/auditoria")
def auditoria_9282(
    anomes: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[dict[str, object]]:
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


@router.post("/autorizar")
def autorizar_9282(anomes: str = "202606") -> dict[str, object]:
    try:
        result = registrar_ajustes_automaticos_9282_postgres(anomes=anomes)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return api_row(result)

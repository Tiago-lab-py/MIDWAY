from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from midway.api.security import AuthUser, require_profiles
from midway.v7.anomaly_repository import anomaly_detail, list_anomalies, module_catalog

router = APIRouter(prefix="/api/anomalias", tags=["anomalias"])


@router.get("")
def listar_anomalias_v7(
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA")),
) -> dict[str, object]:
    payload = list_anomalies()
    return {**payload, "usuario": user.login}


@router.get("/modulos")
def listar_modulos_anomalias_v7(
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR")),
) -> dict[str, object]:
    return {
        "usuario": user.login,
        "items": module_catalog(),
        "regras": {
            "abas": "cada aba representa um módulo de anomalia, não um exemplo pontual",
            "decisao": "algoritmo recomenda; analista decide; divergência exige justificativa",
            "codigo_descricao": "códigos técnicos devem aparecer com descrição humana quando disponível",
        },
    }


@router.get("/{id_anomalia}")
def detalhe_anomalia_v7(
    id_anomalia: str,
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA")),
) -> dict[str, object]:
    detail = anomaly_detail(id_anomalia)
    if not detail:
        raise HTTPException(status_code=404, detail="Anomalia não encontrada.")
    return {
        **detail,
        "usuario": user.login,
    }

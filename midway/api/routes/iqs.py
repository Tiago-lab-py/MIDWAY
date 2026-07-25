from __future__ import annotations

import os
from uuid import uuid4

import duckdb
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text

from midway.api.security import AuthUser, audit_event, require_profiles
from midway.api.serialization import api_rows
from midway.db.postgres import create_postgres_engine, get_config
from midway.export.cloud_exporter import CloudExporter
from midway.transform.tratamento import (
    PROCESSED_DUCKDB_PATH,
    RAW_DUCKDB_PATH,
    criar_tabela_exportacao_iqs,
    exportar_arquivos_iqs,
    exportar_mapeamento_layout_iqs,
    exportar_resumo_iqs,
    sql_literal,
)

router = APIRouter(prefix="/api/iqs", tags=["iqs"])

MODELOS_IQS = [
    {
        "codigo_modelo": "SOBREPOSICAO_TOTAL_UC",
        "nome_modelo": "Sobreposição total por UC",
        "tipo_arquivo": "CSV_IQS",
        "descricao": "Tratamento de UCs com sobreposição total, priorizando remoção/ajuste governado.",
        "perfil_minimo": "GESTOR",
    },
    {
        "codigo_modelo": "SOBREPOSICAO_PARCIAL_UC",
        "nome_modelo": "Sobreposição parcial por UC",
        "tipo_arquivo": "CSV_IQS",
        "descricao": "Tratamento de UCs com interseção parcial de janelas de interrupção.",
        "perfil_minimo": "GESTOR",
    },
    {
        "codigo_modelo": "INTERRUPCAO_SEM_UC_REMANESCENTE",
        "nome_modelo": "Interrupção sem UC remanescente",
        "tipo_arquivo": "CSV_IQS",
        "descricao": "Tratamento de interrupções sem unidades consumidoras remanescentes para exportação IQS.",
        "perfil_minimo": "GESTOR",
    },
    {
        "codigo_modelo": "AJUSTE_9282_RECLAMACAO",
        "nome_modelo": "Ajuste componente/causa 92/82 por reclamação",
        "tipo_arquivo": "CSV_IQS",
        "descricao": "Ajuste de causa não identificada com evidência de reclamação, mantendo revisão governada.",
        "perfil_minimo": "GESTOR",
    },
    {
        "codigo_modelo": "REGRA_RIGIDA_GRUPO_COMP_CAUSA",
        "nome_modelo": "Regra rígida grupo/componente/causa",
        "tipo_arquivo": "CSV_IQS",
        "descricao": "Analisa a classificação atual e sugere correção quando grupo, componente e causa não respeitam a referência IQS.",
        "perfil_minimo": "GESTOR",
    },
]


class GeracaoIqsRequest(BaseModel):
    anomes: str
    modelos: list[str]
    justificativa: str


def _schema() -> str:
    schema = get_config().schema
    if not schema.replace("_", "").isalnum():
        raise HTTPException(status_code=500, detail="Schema PostgreSQL inválido.")
    return schema


def _modelo_por_codigo(codigo: str) -> dict[str, str]:
    for modelo in MODELOS_IQS:
        if modelo["codigo_modelo"] == codigo:
            return modelo
    raise HTTPException(status_code=400, detail=f"Modelo IQS inválido: {codigo}")


@router.get("/modelos")
def listar_modelos_iqs(user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA"))) -> list[dict[str, object]]:
    return MODELOS_IQS


@router.get("/geracoes")
def listar_geracoes_iqs(user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "ANALISTA"))) -> list[dict[str, object]]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(f"SELECT * FROM {schema}.vw_midway_iqs_geracao ORDER BY aprovado_em DESC LIMIT 200")
        ).mappings().all()
    return api_rows([dict(row) for row in rows])


@router.post("/geracoes")
def criar_geracao_iqs(
    payload: GeracaoIqsRequest,
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR")),
) -> dict[str, object]:
    modelos_unicos = list(dict.fromkeys(payload.modelos))
    if not modelos_unicos:
        raise HTTPException(status_code=400, detail="Selecione pelo menos um modelo de geração IQS.")
    if len(payload.justificativa.strip()) < 20:
        raise HTTPException(status_code=400, detail="Justificativa deve ter pelo menos 20 caracteres.")

    modelos = [_modelo_por_codigo(codigo) for codigo in modelos_unicos]
    id_geracao = str(uuid4())
    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_iqs_geracao (
                    id_geracao, anomes, status_geracao, justificativa, aprovado_por, mensagem
                )
                VALUES (
                    :id_geracao, :anomes, 'APROVADA', :justificativa, :aprovado_por,
                    'Pacote aprovado. Geração física dos arquivos será executada pelo processo IQS.'
                )
                """
            ),
            {
                "id_geracao": id_geracao,
                "anomes": payload.anomes,
                "justificativa": payload.justificativa.strip(),
                "aprovado_por": user.login,
            },
        )
        for modelo in modelos:
            con.execute(
                text(
                    f"""
                    INSERT INTO {schema}.midway_iqs_geracao_modelo (
                        id_modelo_geracao, id_geracao, codigo_modelo, nome_modelo, tipo_arquivo
                    )
                    VALUES (
                        :id_modelo_geracao, :id_geracao, :codigo_modelo, :nome_modelo, :tipo_arquivo
                    )
                    """
                ),
                {
                    "id_modelo_geracao": str(uuid4()),
                    "id_geracao": id_geracao,
                    "codigo_modelo": modelo["codigo_modelo"],
                    "nome_modelo": modelo["nome_modelo"],
                    "tipo_arquivo": modelo["tipo_arquivo"],
                },
            )

    audit_event(
        "GERACAO_IQS_APROVADA",
        "midway_iqs_geracao",
        id_geracao,
        user.login,
        {
            "anomes": payload.anomes,
            "modelos": modelos_unicos,
            "qtd_modelos": len(modelos_unicos),
            "justificativa": payload.justificativa.strip(),
        },
        anomes=payload.anomes,
    )
    return {
        "id_geracao": id_geracao,
        "status": "APROVADA",
        "modelos": modelos_unicos,
        "justificativa": payload.justificativa.strip(),
        "download_url": f"/api/iqs/geracoes/{id_geracao}/download"
    }


@router.get("/geracoes/{id_geracao}/download")
def download_geracao_iqs(
    id_geracao: str,
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR")),
):
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        geracao = con.execute(
            text(f"SELECT * FROM {schema}.midway_iqs_geracao WHERE id_geracao = :id_geracao"),
            {"id_geracao": id_geracao}
        ).mappings().first()
        
    if not geracao:
        raise HTTPException(status_code=404, detail="Geração não encontrada.")
        
    anomes = geracao["anomes"]
    
    # Validações dos arquivos do DuckDB
    if not RAW_DUCKDB_PATH.exists() or not PROCESSED_DUCKDB_PATH.exists():
        raise HTTPException(
            status_code=500, 
            detail="Bancos de dados locais (RAW/PROCESSED) não encontrados para gerar os arquivos físicos."
        )
        
    def _gerar_arquivos(tmp_path):
        import logging
        logger = logging.getLogger(f"export_iqs_{id_geracao}")
        logger.setLevel(logging.INFO)
        con_duck = duckdb.connect(str(PROCESSED_DUCKDB_PATH))
        try:
            con_duck.execute(f"ATTACH {sql_literal(RAW_DUCKDB_PATH.as_posix())} AS raw_db (READ_ONLY)")
            tabelas = {linha[0] for linha in con_duck.execute("SHOW TABLES").fetchall()}
            if "adms_iqs_alterados" not in tabelas:
                raise RuntimeError("Tabela adms_iqs_alterados não encontrada no DuckDB processado.")
                
            total_export = criar_tabela_exportacao_iqs(con_duck, logger)
            regionais = con_duck.execute(
                "SELECT DISTINCT REGIONAL_EXPORT FROM adms_iqs_export WHERE REGIONAL_EXPORT IS NOT NULL ORDER BY REGIONAL_EXPORT"
            ).fetchall()
            
            if regionais:
                exportar_arquivos_iqs(con_duck, regionais, tmp_path, "", logger)
                
            exportar_mapeamento_layout_iqs(logger)
            # Resumo será impresso no log
        finally:
            con_duck.close()

    exporter = CloudExporter(anomes=anomes, id_geracao=id_geracao)
    try:
        zip_path = exporter.exportar_pacote_zip(_gerar_arquivos)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar pacote ZIP: {e}")
        
    return FileResponse(
        path=zip_path,
        filename=f"midway_iqs_{anomes}_{id_geracao}.zip",
        media_type="application/zip"
    )


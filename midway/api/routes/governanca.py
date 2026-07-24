from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import text

from midway.api.security import (
    AuthUser,
    audit_event,
    create_session,
    get_current_user,
    hash_password,
    require_profiles,
    revoke_session,
    verify_password,
)
from midway.api.serialization import api_row, api_rows
from midway.db.postgres import create_postgres_engine, get_config, validate_postgres

router = APIRouter(prefix="/api", tags=["governanca"])

EXECUCAO_LOTE_LOCK = threading.Lock()
DUCKDB_BUSY_MAX_TENTATIVAS = 30
DUCKDB_BUSY_INTERVALO_SEGUNDOS = 10


def _duckdb_em_uso(saida: str) -> bool:
    texto = saida.lower()
    return "cannot open file" in texto and ("already open" in texto or "sendo usado" in texto)


class LoginRequest(BaseModel):
    email: str
    senha: str


class UsuarioCreateRequest(BaseModel):
    nome: str
    email: str
    perfil: str
    senha: str


class UsuarioUpdateRequest(BaseModel):
    nome: str
    email: str
    perfil: str
    status_usuario: str = "ATIVO"


class ResetSenhaConfirmRequest(BaseModel):
    codigo: str
    nova_senha: str
    justificativa: str


class ResetSenhaPublicRequest(BaseModel):
    email: str


class ResetSenhaPublicConfirmRequest(BaseModel):
    codigo: str
    nova_senha: str


class AlteracaoRequest(BaseModel):
    anomes: str | None = None
    modulo: str
    entidade: str
    id_entidade: str | None = None
    tipo_alteracao: str = "OUTRO"
    status_alteracao: str = "PENDENTE"
    justificativa: str
    antes: dict[str, object] | None = None
    depois: dict[str, object] | None = None


class DecisaoAlteracaoRequest(BaseModel):
    justificativa: str


class ExecucaoRequest(BaseModel):
    tipo_lote: str
    anomes: str = "202607"
    parametros: dict[str, object] | None = None
    forcar: bool = False


class PerfilPermissaoUpdateRequest(BaseModel):
    pode_visualizar: bool
    pode_editar: bool


PERFIS_VALIDOS = {"ADM", "GESTOR", "ANALISTA", "CONSULTA", "AUDITOR"}
STATUS_USUARIO_VALIDOS = {"ATIVO", "BLOQUEADO", "INATIVO"}

PERFIS_DESCRICOES = {
    "ADM": "Administração completa da plataforma.",
    "GESTOR": "Decisão executiva, aprovações e acompanhamento operacional.",
    "ANALISTA": "Tratamento técnico, análise e propostas de correção.",
    "CONSULTA": "Acesso de leitura a painéis e evidências.",
    "AUDITOR": "Leitura de trilhas, execuções e evidências auditáveis.",
}

PAGINAS_PERMISSAO = {
    "dashboard": "Dashboard",
    "produto": "Produto",
    "executivo": "Executivo",
    "anomalias": "Anomalias",
    "analise_tecnica": "Análise Técnica",
    "administracao": "Administração",
}

EXECUCOES_PERMITIDAS = {
    "extract": {
        "titulo": "run.bat extract — Atualizar RAW ADMS",
        "descricao": "Extrai dados do ADMS para DuckDB RAW.",
        "etapas": [{"module": "midway.extract.adms", "env": {}}],
    },
    "registrar": {
        "titulo": "run.bat registrar — Registrar RAW existente",
        "descricao": "Registra DuckDB RAW já existente sem reextrair.",
        "etapas": [{"module": "midway.extract.adms", "env": {"REGISTRAR_RAW": "1"}}],
    },
    "reextrair": {
        "titulo": "run.bat reextrair — Reextrair RAW ADMS",
        "descricao": "Refaz extração ADMS com REEXTRAIR=1.",
        "etapas": [{"module": "midway.extract.adms", "env": {"REEXTRAIR": "1"}}],
    },
    "tratamento": {
        "titulo": "run.bat tratamento — Processar RAW para SILVER",
        "descricao": "Executa tratamento e materializa base processada.",
        "etapas": [{"module": "midway.transform.tratamento", "env": {}}],
    },
    "reprocessar": {
        "titulo": "run.bat reprocessar — Reprocessar SILVER",
        "descricao": "Refaz tratamento com REPROCESSAR=1.",
        "etapas": [{"module": "midway.transform.tratamento", "env": {"REPROCESSAR": "1"}}],
    },
    "etl": {
        "titulo": "run.bat etl — Pipeline ETL Central Completo (Fase 1 a 4)",
        "descricao": "Executa de forma centralizada todas as etapas do ETL 100% Python (Fase 1, 2, 3 e 4).",
        "etapas": [{"module": "midway.pipeline.etl", "env": {}}],
    },
    "fase1": {
        "titulo": "FASE 1 — Extrações Sequenciais (Início de Mês)",
        "descricao": "Executa em sequência todas as extrações de início de mês: ADMS, UCs Faturadas, Reclamações DBGUO, Serviços ADMS e Referências IQS.",
        "etapas": [
            {"module": "midway.extract.adms", "env": {}},
            {"module": "midway.extract.uc_fatura", "env": {}},
            {"module": "midway.extract.reclamacoes_dbguo", "env": {}},
            {"module": "midway.extract.adms_servicos", "env": {}},
            {"module": "midway.extract.referencia_componente_causa", "env": {}},
            {"module": "midway.extract.metas_uc", "env": {}},
            {"module": "midway.extract.vrc", "env": {}},
            {"module": "midway.extract.consumidores", "env": {}},
        ],
    },
    "fase2": {
        "titulo": "FASE 2 — Tratamento e Normalização",
        "descricao": "Processa anomalias, higieniza sobreposições temporais e exporta os arquivos regulatórios CSV de carga (CSL, LES, NRO, NRT, OES).",
        "etapas": [{"module": "midway.transform.tratamento", "env": {}}],
    },
    "fase3": {
        "titulo": "FASE 3 — Apuração Prévia Regulatória",
        "descricao": "Materializa as tabelas GOLD e calcula os indicadores macro de DEC/FEC, DIC/FIC e estimativa de compensação financeira.",
        "etapas": [{"module": "midway.apuracao.previa", "env": {}}],
    },
    "fase4": {
        "titulo": "FASE 4 — Analytics e Propostas de Anomalia",
        "descricao": "Alimenta a base de Outliers por UC e executa os agentes inteligentes do motor de anomalias.",
        "etapas": [
            {"module": "midway.analytics.outlier_uc", "env": {}},
            {"module": "midway.modulos.orquestrador", "env": {}},
        ],
    },
    "full": {
        "titulo": "run.bat full — Extração + tratamento (Legado)",
        "descricao": "Executa extração RAW e tratamento SILVER em sequência.",
        "etapas": [
            {"module": "midway.extract.adms", "env": {}},
            {"module": "midway.transform.tratamento", "env": {}},
        ],
    },
    "full_mais_apuracao": {
        "titulo": "run.bat full_mais_apuracao — Pipeline completo",
        "descricao": "Executa extração, tratamento, bases auxiliares, GOLD e exportações auxiliares.",
        "etapas": [
            {"module": "midway.extract.adms", "env": {}},
            {"module": "midway.transform.tratamento", "env": {}},
            {"module": "midway.extract.consumidores", "env": {}},
            {"module": "midway.extract.uc_fatura", "env": {}},
            {"module": "midway.apuracao.previa", "env": {}},
            {"module": "midway.analytics.outlier_uc", "env": {}},
            {"module": "midway.auditoria.sobreposicoes", "env": {}},
        ],
    },
    "exportar": {
        "titulo": "run.bat exportar — Gerar CSVs IQS",
        "descricao": "Regenera CSVs finais sem refazer tratamento.",
        "etapas": [{"module": "midway.export.csv_iqs", "env": {}}],
    },
    "apuracao_parcial": {
        "titulo": "run.bat apuracao_parcial — Gerar GOLD",
        "descricao": "Gera camadas GOLD e outliers usados pela análise.",
        "etapas": [
            {"module": "midway.apuracao.previa", "env": {}},
            {"module": "midway.analytics.outlier_uc", "env": {}},
        ],
    },
    "consumidores": {
        "titulo": "run.bat consumidores — Extrair consumidores IQS",
        "descricao": "Extrai consumidores IQS para uso nas camadas GOLD.",
        "etapas": [{"module": "midway.extract.consumidores", "env": {}}],
    },
    "uc_fatura": {
        "titulo": "run.bat uc_fatura — Extrair UCs faturadas",
        "descricao": "Extrai UCs consideradas na apuração.",
        "etapas": [{"module": "midway.extract.uc_fatura", "env": {}}],
    },
    "vrc": {
        "titulo": "run.bat vrc — Extrair VRC",
        "descricao": "Extrai VRC IQS sob demanda.",
        "etapas": [{"module": "midway.extract.vrc", "env": {}}],
    },
    "reextrair_vrc": {
        "titulo": "run.bat reextrair_vrc — Reextrair VRC",
        "descricao": "Reextrai VRC IQS sob demanda com REEXTRAIR_VRC=1.",
        "etapas": [{"module": "midway.extract.vrc", "env": {"REEXTRAIR_VRC": "1"}}],
    },
    "metas_uc": {
        "titulo": "run.bat metas_uc — Extrair metas UC",
        "descricao": "Extrai metas UC IQS sob demanda.",
        "etapas": [{"module": "midway.extract.metas_uc", "env": {}}],
    },
    "reextrair_metas_uc": {
        "titulo": "run.bat reextrair_metas_uc — Reextrair metas UC",
        "descricao": "Reextrai metas UC IQS sob demanda com REEXTRAIR_METAS_UC=1.",
        "etapas": [{"module": "midway.extract.metas_uc", "env": {"REEXTRAIR_METAS_UC": "1"}}],
    },
    "referencia_iqs": {
        "titulo": "run.bat referencia_iqs — Referência componente/causa",
        "descricao": "Extrai referência de componente/causa IQS.",
        "etapas": [{"module": "midway.extract.referencia_componente_causa", "env": {}}],
    },
    "reextrair_referencia_iqs": {
        "titulo": "run.bat reextrair_referencia_iqs — Reextrair referência IQS",
        "descricao": "Reextrai referência componente/causa com REEXTRAIR_REFERENCIA_IQS=1.",
        "etapas": [
            {"module": "midway.extract.referencia_componente_causa", "env": {"REEXTRAIR_REFERENCIA_IQS": "1"}}
        ],
    },
    "sincronizar_iqs_raw": {
        "titulo": "run.bat sincronizar_iqs_raw — Sincronizar IQS RAW",
        "descricao": "Sincroniza data/raw/iqs_raw_<ANOMES>.duckdb para o processado.",
        "etapas": [{"script": "tools/sincronizar_iqs_raw.py", "env": {}}],
    },
    "extrair_dbguo_reclamacoes": {
        "titulo": "run.bat extrair_dbguo_reclamacoes — Extrair reclamações",
        "descricao": "Extrai reclamações DBGUO para data/raw.",
        "etapas": [{"module": "midway.extract.reclamacoes_dbguo", "env": {}}],
    },
    "extrair_adms_servicos": {
        "titulo": "run.bat extrair_adms_servicos — Atualizar RAW serviços",
        "descricao": "Extrai serviços ADMS usados nas correções 9282.",
        "etapas": [{"module": "midway.extract.adms_servicos", "env": {}}],
    },
    "dbguo_reclamacoes": {
        "titulo": "run.bat dbguo_reclamacoes — Processar reclamações",
        "descricao": "Materializa SILVER/GOLD de reclamações DBGUO.",
        "etapas": [{"module": "midway.transform.dbguo_reclamacoes_silver", "env": {}}],
    },
    "reclamacoes_servicos": {
        "titulo": "run.bat reclamacoes_servicos — Reclamações e serviços",
        "descricao": (
            "Materializa reclamações DBGUO e vínculos com ocorrências; serviços ADMS entram como evidência "
            "quando data/raw/adms_servicos_raw_<ANOMES>.duckdb já estiver disponível."
        ),
        "etapas": [{"module": "midway.transform.dbguo_reclamacoes_silver", "env": {}}],
    },
    "orquestrador": {
        "titulo": "run.bat orquestrador — Tratativas em massa (Orquestrador)",
        "descricao": "Executa todos os módulos de anomalias (Sobreposições, Interrupção sem UC, etc) e gera as Propostas de Tratamento.",
        "etapas": [{"module": "midway.modulos.orquestrador", "env": {}}],
    },
    "simulacao_ise": {
        "titulo": "run.bat simulacao_ise — Dia crítico / ISE",
        "descricao": "Materializa gold_simulacao_ise_uc e exporta evidências de potencial ISE/DISE.",
        "etapas": [{"script": "tools/gerar_simulacao_ise.py", "env": {}}],
    },
    "auditar_ajuste_inicio_manobra": {
        "titulo": "run.bat auditar_ajuste_inicio_manobra — Auditoria manobra",
        "descricao": "Gera auditoria de ajuste de início de manobra.",
        "etapas": [{"module": "midway.auditoria.ajuste_inicio_manobra", "env": {}}],
    },
    "exportacoes_auxiliares": {
        "titulo": "run.bat exportacoes_auxiliares — Exportações auxiliares",
        "descricao": "Gera sobreposições, interrupções sem UC e normalização de datas.",
        "etapas": [
            {"module": "midway.auditoria.sobreposicoes", "env": {}},
            {"module": "midway.auditoria.interrupcao_sem_uc", "env": {}},
            {"module": "midway.export.normalizar_datas_iqs", "env": {}},
        ],
    },
    "metricas_qualidade": {
        "titulo": "run.bat metricas_qualidade — Métricas de qualidade",
        "descricao": "Gera métricas de qualidade dos dados tratados.",
        "etapas": [{"script": "tools/gerar_metricas_qualidade.py", "env": {}}],
    },
    "amostras_auditoria": {
        "titulo": "run.bat amostras_auditoria — Amostras de auditoria",
        "descricao": "Exporta amostras de auditoria orientadas por risco.",
        "etapas": [{"script": "tools/exportar_amostras_auditoria.py", "env": {}}],
    },
    "anomalias": {
        "titulo": "run.bat anomalias_setup — Atualizar Anomalias",
        "descricao": "Recarrega anomalias a partir de RAW/SILVER/GOLD.",
        "etapas": [
            {"module": "midway.db.apply_sql", "args": ["008_nucleo_anomalias_v7.sql"], "env": {}},
            {"module": "midway.v7.generate_real_anomalies", "env": {}},
            {"module": "midway.db.postgres", "env": {}},
        ],
    },
    "anomalias_validar": {
        "titulo": "run.bat anomalias_validar — Validar Anomalias",
        "descricao": "Executa teste do núcleo funcional de anomalias.",
        "etapas": [{"module": "unittest", "args": ["tests.test_v7_real_anomalies"], "env": {}}],
    },
}


def _schema() -> str:
    schema = get_config().schema
    if not schema.replace("_", "").isalnum():
        raise HTTPException(status_code=500, detail="Schema PostgreSQL inválido.")
    return schema


def _public_user(row: dict[str, object]) -> dict[str, object]:
    email = row.get("email") or row["login"]
    return {
        "id_usuario": str(row["id_usuario"]),
        "login": email,
        "nome": row["nome"],
        "email": email,
        "perfil": row["perfil"],
    }


def _normalize_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise HTTPException(status_code=400, detail="E-mail inválido.")
    return email


def _normalize_perfil(value: str) -> str:
    perfil = value.upper().strip()
    if perfil not in PERFIS_VALIDOS:
        raise HTTPException(status_code=400, detail="Perfil inválido.")
    return perfil


def _normalize_status_usuario(value: str) -> str:
    status = value.upper().strip()
    if status not in STATUS_USUARIO_VALIDOS:
        raise HTTPException(status_code=400, detail="Status de usuário inválido.")
    return status


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _atualizar_lote(id_lote: str, status: str, mensagem: str) -> None:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_execucao_lote
                SET status_lote = :status_lote,
                    mensagem = :mensagem,
                    finalizado_em = CASE
                        WHEN :status_lote IN ('CONCLUIDO', 'ERRO', 'CANCELADO') THEN now()
                        ELSE finalizado_em
                    END
                WHERE id_lote = :id_lote
                """
            ),
            {"id_lote": id_lote, "status_lote": status, "mensagem": mensagem[-6000:]},
        )


def _executar_lote_background(id_lote: str, tipo_lote: str, anomes: str, forcar: bool = False) -> None:
    config = EXECUCOES_PERMITIDAS[tipo_lote]
    root = _repo_root()
    env_base = os.environ.copy()
    env_base["ANOMES"] = anomes
    if forcar:
        env_base["REEXTRAIR"] = "1"
        env_base["REPROCESSAR"] = "1"
        env_base["REGISTRAR_RAW"] = "0"
        env_base["REEXTRAIR_VRC"] = "1"
        env_base["REEXTRAIR_METAS_UC"] = "1"
        env_base["REEXTRAIR_REFERENCIA_IQS"] = "1"
        env_base["REEXTRAIR_DBGUO"] = "1"
        env_base["REEXTRAIR_ADMS_SERVICOS"] = "1"
    _atualizar_lote(
        id_lote,
        "ABERTO",
        f"Solicitação recebida: {config['titulo']}{' (FORÇAR REPROCESSAMENTO)' if forcar else ''}. Aguardando fila de execução.",
    )
    saidas: list[str] = []
    try:
        with EXECUCAO_LOTE_LOCK:
            _atualizar_lote(id_lote, "PROCESSANDO", f"Processamento iniciado: {config['titulo']}.")
            for etapa in config["etapas"]:
                env = {**env_base, **etapa.get("env", {})}
                args = [str(arg) for arg in etapa.get("args", [])]
                module = etapa.get("module")
                script = etapa.get("script")
                if module:
                    command = [sys.executable, "-m", str(module), *args]
                    command_label = f"python -m {module}" + (f" {' '.join(args)}" if args else "")
                elif script:
                    script_path = root / str(script)
                    command = [sys.executable, str(script_path), *args]
                    command_label = f"python {script}" + (f" {' '.join(args)}" if args else "")
                else:
                    raise RuntimeError("Etapa de processamento sem módulo ou script.")
                process = None
                saida = ""
                for tentativa in range(1, DUCKDB_BUSY_MAX_TENTATIVAS + 1):
                    process = subprocess.run(
                        command,
                        cwd=str(root),
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=60 * 60 * 6,
                        check=False,
                    )
                    saida = "\n".join([process.stdout.strip(), process.stderr.strip()]).strip()
                    if process.returncode == 0 or not _duckdb_em_uso(saida) or tentativa == DUCKDB_BUSY_MAX_TENTATIVAS:
                        break
                    _atualizar_lote(
                        id_lote,
                        "PROCESSANDO",
                        f"{command_label}: DuckDB em uso por outro processo. Nova tentativa {tentativa + 1}/{DUCKDB_BUSY_MAX_TENTATIVAS} em {DUCKDB_BUSY_INTERVALO_SEGUNDOS} segundos.",
                    )
                    time.sleep(DUCKDB_BUSY_INTERVALO_SEGUNDOS)
                if saida:
                    saidas.append(f"$ {command_label}\n{saida}")
                if process and process.returncode != 0:
                    _atualizar_lote(id_lote, "ERRO", "\n\n".join(saidas) or f"Falha em {command_label}.")
                    return
            _atualizar_lote(id_lote, "CONCLUIDO", "\n\n".join(saidas) or "Processamento concluído.")
    except Exception as exc:
        _atualizar_lote(id_lote, "ERRO", f"Erro ao executar processamento: {exc}")


@router.post("/auth/login")
def login(payload: LoginRequest, request: Request) -> dict[str, object]:
    schema = _schema()
    email = _normalize_email(payload.email)
    engine = create_postgres_engine()
    with engine.begin() as con:
        row = con.execute(
            text(
                f"""
                SELECT id_usuario, login, nome, email, perfil, senha_hash, status_usuario, bloqueado_ate
                FROM {schema}.midway_usuario
                WHERE lower(coalesce(email, login)) = :email
                """
            ),
            {"email": email},
        ).mappings().first()

        if not row or row["status_usuario"] != "ATIVO":
            raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

        if not verify_password(payload.senha, str(row["senha_hash"])):
            con.execute(
                text(
                    f"""
                    UPDATE {schema}.midway_usuario
                    SET tentativas_invalidas = tentativas_invalidas + 1,
                        atualizado_em = now()
                    WHERE id_usuario = :id_usuario
                    """
                ),
                {"id_usuario": row["id_usuario"]},
            )
            raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_usuario
                SET ultimo_login_em = now(),
                    tentativas_invalidas = 0,
                    atualizado_em = now()
                WHERE id_usuario = :id_usuario
                """
            ),
            {"id_usuario": row["id_usuario"]},
        )

    session = create_session(str(row["id_usuario"]), request)
    audit_event(
        "LOGIN",
        "midway_usuario",
        str(row["id_usuario"]),
        str(row["login"]),
        {"perfil": row["perfil"]},
    )
    return {
        **session,
        "user": _public_user(dict(row)),
    }


@router.post("/auth/logout")
def logout(request: Request, user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    authorization = request.headers.get("authorization") if request else None
    if authorization and authorization.lower().startswith("bearer "):
        revoke_session(authorization.split(" ", 1)[1].strip())
    audit_event("LOGOUT", "midway_usuario", user.id_usuario, user.login)
    return {"status": "ok"}


@router.get("/auth/me")
def me(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    return api_row(user.__dict__)


@router.post("/auth/reset-senha/solicitar")
def solicitar_reset_senha_publico(
    payload: ResetSenhaPublicRequest,
    request: Request,
) -> dict[str, object]:
    schema = _schema()
    email = _normalize_email(payload.email)
    codigo = f"{secrets.randbelow(10000):04d}"
    id_reset = str(uuid4())
    ip_origem = request.client.host if request and request.client else None

    engine = create_postgres_engine()
    with engine.begin() as con:
        usuario = con.execute(
            text(
                f"""
                SELECT id_usuario, login, email, perfil, status_usuario
                FROM {schema}.midway_usuario
                WHERE lower(coalesce(email, login)) = :email
                """
            ),
            {"email": email},
        ).mappings().first()
        if not usuario or usuario["status_usuario"] != "ATIVO":
            raise HTTPException(status_code=404, detail="Usuário ativo não encontrado para este e-mail.")

        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_reset_senha
                SET status_reset = 'CANCELADO',
                    atualizado_em = now()
                WHERE id_usuario = :id_usuario
                  AND status_reset = 'PENDENTE'
                """
            ),
            {"id_usuario": usuario["id_usuario"]},
        )
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_reset_senha (
                    id_reset, id_usuario, solicitado_por, codigo_hash, expira_em, ip_origem, justificativa
                )
                VALUES (
                    :id_reset, :id_usuario, :solicitado_por, :codigo_hash, now() + interval '10 minutes',
                    :ip_origem, :justificativa
                )
                """
            ),
            {
                "id_reset": id_reset,
                "id_usuario": usuario["id_usuario"],
                "solicitado_por": email,
                "codigo_hash": hash_password(codigo),
                "ip_origem": ip_origem,
                "justificativa": "Solicitação realizada na tela inicial.",
            },
        )
        reset_row = con.execute(
            text(
                f"""
                SELECT id_reset, expira_em
                FROM {schema}.midway_reset_senha
                WHERE id_reset = :id_reset
                """
            ),
            {"id_reset": id_reset},
        ).mappings().one()

    audit_event(
        "RESET_SENHA_SOLICITADO_LOGIN",
        "midway_usuario",
        str(usuario["id_usuario"]),
        email,
        {"perfil": usuario["perfil"], "id_reset": id_reset},
    )
    return {
        "id_reset": id_reset,
        "login": usuario.get("email") or usuario["login"],
        "codigo": codigo,
        "expira_em": reset_row["expira_em"],
        "status": "pendente",
    }


@router.post("/auth/reset-senha/{id_reset}/confirmar")
def confirmar_reset_senha_publico(
    id_reset: str,
    payload: ResetSenhaPublicConfirmRequest,
) -> dict[str, object]:
    request_payload = ResetSenhaConfirmRequest(
        codigo=payload.codigo,
        nova_senha=payload.nova_senha,
        justificativa="Reset confirmado na tela inicial pelo próprio usuário.",
    )
    return _confirmar_reset_senha(id_reset, request_payload, confirmado_por="autoatendimento")


@router.get("/governanca/usuarios")
def listar_usuarios(
    user: AuthUser = Depends(require_profiles("ADM")),
) -> list[dict[str, object]]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(f"SELECT * FROM {schema}.vw_midway_governanca_usuarios ORDER BY email")
        ).mappings().all()
    return api_rows([dict(row) for row in rows])


@router.post("/governanca/usuarios")
def criar_usuario(
    payload: UsuarioCreateRequest,
    user: AuthUser = Depends(require_profiles("ADM")),
) -> dict[str, object]:
    perfil = _normalize_perfil(payload.perfil)
    email = _normalize_email(payload.email)
    if len(payload.senha) < 12:
        raise HTTPException(status_code=400, detail="Senha deve ter no mínimo 12 caracteres.")

    schema = _schema()
    id_usuario = str(uuid4())
    engine = create_postgres_engine()
    with engine.begin() as con:
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_usuario (
                    id_usuario, login, nome, email, perfil, senha_hash, criado_por, atualizado_por
                )
                VALUES (
                    :id_usuario, :login, :nome, :email, :perfil, :senha_hash, :criado_por, :atualizado_por
                )
                """
            ),
            {
                "id_usuario": id_usuario,
                "login": email,
                "nome": payload.nome.strip(),
                "email": email,
                "perfil": perfil,
                "senha_hash": hash_password(payload.senha),
                "criado_por": user.login,
                "atualizado_por": user.login,
            },
        )

    audit_event(
        "USUARIO_CRIADO",
        "midway_usuario",
        id_usuario,
        user.login,
        {"email": email, "perfil": perfil},
    )
    return {"id_usuario": id_usuario, "status": "criado"}


@router.patch("/governanca/usuarios/{id_usuario}")
def atualizar_usuario(
    id_usuario: str,
    payload: UsuarioUpdateRequest,
    user: AuthUser = Depends(require_profiles("ADM")),
) -> dict[str, object]:
    perfil = _normalize_perfil(payload.perfil)
    status_usuario = _normalize_status_usuario(payload.status_usuario)
    email = _normalize_email(payload.email)
    nome = payload.nome.strip()
    if len(nome) < 3:
        raise HTTPException(status_code=400, detail="Nome deve ter no mínimo 3 caracteres.")

    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        row = con.execute(
            text(
                f"""
                SELECT id_usuario, login, email, perfil, status_usuario
                FROM {schema}.midway_usuario
                WHERE id_usuario = :id_usuario
                """
            ),
            {"id_usuario": id_usuario},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        if str(row["id_usuario"]) == user.id_usuario and status_usuario != "ATIVO":
            raise HTTPException(status_code=400, detail="Não é permitido inativar ou bloquear o próprio usuário.")

        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_usuario
                SET login = :email,
                    nome = :nome,
                    email = :email,
                    perfil = :perfil,
                    status_usuario = :status_usuario,
                    atualizado_por = :atualizado_por,
                    atualizado_em = now()
                WHERE id_usuario = :id_usuario
                """
            ),
            {
                "id_usuario": id_usuario,
                "email": email,
                "nome": nome,
                "perfil": perfil,
                "status_usuario": status_usuario,
                "atualizado_por": user.login,
            },
        )
        if status_usuario != "ATIVO":
            con.execute(
                text(
                    f"""
                    UPDATE {schema}.midway_sessao
                    SET revogado_em = now()
                    WHERE id_usuario = :id_usuario
                      AND revogado_em IS NULL
                    """
                ),
                {"id_usuario": id_usuario},
            )

    audit_event(
        "USUARIO_ATUALIZADO",
        "midway_usuario",
        id_usuario,
        user.login,
        {"email": email, "perfil": perfil, "status_usuario": status_usuario},
    )
    return {"id_usuario": id_usuario, "status": "atualizado"}


@router.delete("/governanca/usuarios/{id_usuario}")
def inativar_usuario(
    id_usuario: str,
    user: AuthUser = Depends(require_profiles("ADM")),
) -> dict[str, object]:
    if id_usuario == user.id_usuario:
        raise HTTPException(status_code=400, detail="Não é permitido inativar o próprio usuário.")
    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        row = con.execute(
            text(
                f"""
                SELECT id_usuario, login, email, perfil
                FROM {schema}.midway_usuario
                WHERE id_usuario = :id_usuario
                """
            ),
            {"id_usuario": id_usuario},
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")
        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_usuario
                SET status_usuario = 'INATIVO',
                    atualizado_por = :atualizado_por,
                    atualizado_em = now()
                WHERE id_usuario = :id_usuario
                """
            ),
            {"id_usuario": id_usuario, "atualizado_por": user.login},
        )
        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_sessao
                SET revogado_em = now()
                WHERE id_usuario = :id_usuario
                  AND revogado_em IS NULL
                """
            ),
            {"id_usuario": id_usuario},
        )
    audit_event(
        "USUARIO_INATIVADO",
        "midway_usuario",
        id_usuario,
        user.login,
        {"email": row.get("email") or row["login"], "perfil": row["perfil"]},
    )
    return {"id_usuario": id_usuario, "status": "inativado"}


@router.get("/governanca/perfis")
def listar_perfis(user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "AUDITOR"))) -> list[dict[str, object]]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(
                f"""
                SELECT perfil, pagina, pode_visualizar, pode_editar, atualizado_por, atualizado_em
                FROM {schema}.vw_midway_governanca_permissoes
                ORDER BY perfil, pagina
                """
            )
        ).mappings().all()

    permissoes_por_perfil: dict[str, list[dict[str, object]]] = {perfil: [] for perfil in sorted(PERFIS_VALIDOS)}
    for row in rows:
        item = dict(row)
        pagina = str(item["pagina"])
        permissoes_por_perfil.setdefault(str(item["perfil"]), []).append(
            {
                "pagina": pagina,
                "pagina_label": PAGINAS_PERMISSAO.get(pagina, pagina),
                "pode_visualizar": bool(item["pode_visualizar"]),
                "pode_editar": bool(item["pode_editar"]),
                "atualizado_por": item.get("atualizado_por"),
                "atualizado_em": item.get("atualizado_em"),
            }
        )

    return api_rows(
        [
            {
                "perfil": perfil,
                "descricao": PERFIS_DESCRICOES.get(perfil, perfil),
                "permissoes": permissoes_por_perfil.get(perfil, []),
            }
            for perfil in sorted(PERFIS_VALIDOS)
        ]
    )


@router.patch("/governanca/perfis/{perfil}/permissoes/{pagina}")
def atualizar_permissao_perfil(
    perfil: str,
    pagina: str,
    payload: PerfilPermissaoUpdateRequest,
    user: AuthUser = Depends(require_profiles("ADM")),
) -> dict[str, object]:
    perfil_normalizado = _normalize_perfil(perfil)
    pagina_normalizada = pagina.strip().lower()
    if pagina_normalizada not in PAGINAS_PERMISSAO:
        raise HTTPException(status_code=400, detail="Página inválida.")
    if perfil_normalizado == "ADM" and (not payload.pode_visualizar or not payload.pode_editar):
        raise HTTPException(status_code=400, detail="O perfil ADM deve manter visualizar e editar ativos.")

    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_perfil_permissao (
                    perfil, pagina, pode_visualizar, pode_editar, atualizado_por, atualizado_em
                )
                VALUES (
                    :perfil, :pagina, :pode_visualizar, :pode_editar, :atualizado_por, now()
                )
                ON CONFLICT (perfil, pagina)
                DO UPDATE SET
                    pode_visualizar = EXCLUDED.pode_visualizar,
                    pode_editar = EXCLUDED.pode_editar,
                    atualizado_por = EXCLUDED.atualizado_por,
                    atualizado_em = now()
                """
            ),
            {
                "perfil": perfil_normalizado,
                "pagina": pagina_normalizada,
                "pode_visualizar": payload.pode_visualizar,
                "pode_editar": payload.pode_editar,
                "atualizado_por": user.login,
            },
        )
    audit_event(
        "PERFIL_PERMISSAO_ATUALIZADA",
        "midway_perfil_permissao",
        f"{perfil_normalizado}:{pagina_normalizada}",
        user.login,
        {
            "perfil": perfil_normalizado,
            "pagina": pagina_normalizada,
            "pode_visualizar": payload.pode_visualizar,
            "pode_editar": payload.pode_editar,
        },
    )
    return {
        "perfil": perfil_normalizado,
        "pagina": pagina_normalizada,
        "pode_visualizar": payload.pode_visualizar,
        "pode_editar": payload.pode_editar,
        "status": "atualizado",
    }


@router.post("/governanca/usuarios/{id_usuario}/reset-senha/preparar")
def preparar_reset_senha(
    id_usuario: str,
    request: Request,
    user: AuthUser = Depends(require_profiles("ADM")),
) -> dict[str, object]:
    schema = _schema()
    codigo = f"{secrets.randbelow(10000):04d}"
    id_reset = str(uuid4())
    ip_origem = request.client.host if request and request.client else None

    engine = create_postgres_engine()
    with engine.begin() as con:
        usuario = con.execute(
            text(
                f"""
                SELECT id_usuario, login, email, perfil, status_usuario
                FROM {schema}.midway_usuario
                WHERE id_usuario = :id_usuario
                """
            ),
            {"id_usuario": id_usuario},
        ).mappings().first()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuário não encontrado.")

        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_reset_senha
                SET status_reset = 'CANCELADO',
                    atualizado_em = now()
                WHERE id_usuario = :id_usuario
                  AND status_reset = 'PENDENTE'
                """
            ),
            {"id_usuario": id_usuario},
        )
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_reset_senha (
                    id_reset, id_usuario, solicitado_por, codigo_hash, expira_em, ip_origem
                )
                VALUES (
                    :id_reset, :id_usuario, :solicitado_por, :codigo_hash, now() + interval '10 minutes', :ip_origem
                )
                """
            ),
            {
                "id_reset": id_reset,
                "id_usuario": id_usuario,
                "solicitado_por": user.login,
                "codigo_hash": hash_password(codigo),
                "ip_origem": ip_origem,
            },
        )
        reset_row = con.execute(
            text(
                f"""
                SELECT id_reset, expira_em
                FROM {schema}.midway_reset_senha
                WHERE id_reset = :id_reset
                """
            ),
            {"id_reset": id_reset},
        ).mappings().one()

    audit_event(
        "RESET_SENHA_PREPARADO",
        "midway_usuario",
        id_usuario,
        user.login,
        {"email": usuario.get("email") or usuario["login"], "perfil": usuario["perfil"], "id_reset": id_reset},
    )
    return {
        "id_reset": id_reset,
        "id_usuario": id_usuario,
        "login": usuario.get("email") or usuario["login"],
        "codigo": codigo,
        "expira_em": reset_row["expira_em"],
        "status": "pendente",
    }


def _confirmar_reset_senha(
    id_reset: str,
    payload: ResetSenhaConfirmRequest,
    confirmado_por: str,
) -> dict[str, object]:
    codigo = payload.codigo.strip()
    if len(codigo) != 4 or not codigo.isdigit():
        raise HTTPException(status_code=400, detail="Código deve conter 4 dígitos.")
    if len(payload.nova_senha) < 12:
        raise HTTPException(status_code=400, detail="Nova senha deve ter no mínimo 12 caracteres.")
    if len(payload.justificativa.strip()) < 8:
        raise HTTPException(status_code=400, detail="Informe uma justificativa para o reset.")

    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        reset_row = con.execute(
            text(
                f"""
                SELECT
                    r.id_reset,
                    r.id_usuario,
                    r.codigo_hash,
                    r.status_reset,
                    r.expira_em,
                    (r.expira_em < now()) AS expirado,
                    r.tentativas,
                    u.login,
                    u.email,
                    u.perfil
                FROM {schema}.midway_reset_senha r
                JOIN {schema}.midway_usuario u
                  ON u.id_usuario = r.id_usuario
                WHERE r.id_reset = :id_reset
                FOR UPDATE
                """
            ),
            {"id_reset": id_reset},
        ).mappings().first()
        if not reset_row:
            raise HTTPException(status_code=404, detail="Reset de senha não encontrado.")
        if reset_row["status_reset"] != "PENDENTE":
            raise HTTPException(status_code=400, detail="Reset de senha não está pendente.")

        if reset_row["expirado"]:
            con.execute(
                text(
                    f"""
                    UPDATE {schema}.midway_reset_senha
                    SET status_reset = 'EXPIRADO',
                        atualizado_em = now()
                    WHERE id_reset = :id_reset
                    """
                ),
                {"id_reset": id_reset},
            )
            raise HTTPException(status_code=400, detail="Código expirado. Gere um novo reset.")

        if not verify_password(codigo, str(reset_row["codigo_hash"])):
            tentativas = int(reset_row["tentativas"] or 0) + 1
            status = "CANCELADO" if tentativas >= 3 else "PENDENTE"
            con.execute(
                text(
                    f"""
                    UPDATE {schema}.midway_reset_senha
                    SET tentativas = :tentativas,
                        status_reset = :status_reset,
                        atualizado_em = now()
                    WHERE id_reset = :id_reset
                    """
                ),
                {"tentativas": tentativas, "status_reset": status, "id_reset": id_reset},
            )
            raise HTTPException(status_code=400, detail="Código inválido.")

        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_usuario
                SET senha_hash = :senha_hash,
                    tentativas_invalidas = 0,
                    bloqueado_ate = NULL,
                    status_usuario = 'ATIVO',
                    atualizado_por = :atualizado_por,
                    atualizado_em = now()
                WHERE id_usuario = :id_usuario
                """
            ),
            {
                "senha_hash": hash_password(payload.nova_senha),
                "atualizado_por": user.login,
                "id_usuario": reset_row["id_usuario"],
            },
        )
        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_sessao
                SET revogado_em = now()
                WHERE id_usuario = :id_usuario
                  AND revogado_em IS NULL
                """
            ),
            {"id_usuario": reset_row["id_usuario"]},
        )
        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_reset_senha
                SET status_reset = 'CONFIRMADO',
                    confirmado_por = :confirmado_por,
                    confirmado_em = now(),
                    justificativa = :justificativa,
                    atualizado_em = now()
                WHERE id_reset = :id_reset
                """
            ),
            {
                "confirmado_por": confirmado_por,
                "justificativa": payload.justificativa.strip(),
                "id_reset": id_reset,
            },
        )

    audit_event(
        "RESET_SENHA_CONFIRMADO",
        "midway_usuario",
        str(reset_row["id_usuario"]),
        confirmado_por,
        {"email": reset_row.get("email") or reset_row["login"], "perfil": reset_row["perfil"], "id_reset": id_reset},
    )
    return {"status": "confirmado", "id_reset": id_reset, "login": reset_row.get("email") or reset_row["login"]}


@router.post("/governanca/reset-senha/{id_reset}/confirmar")
def confirmar_reset_senha(
    id_reset: str,
    payload: ResetSenhaConfirmRequest,
    user: AuthUser = Depends(require_profiles("ADM")),
) -> dict[str, object]:
    return _confirmar_reset_senha(id_reset, payload, confirmado_por=user.login)


@router.get("/governanca/reset-senha")
def listar_reset_senha(user: AuthUser = Depends(require_profiles("ADM"))) -> list[dict[str, object]]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(f"SELECT * FROM {schema}.vw_midway_governanca_reset_senha ORDER BY criado_em DESC LIMIT 100")
        ).mappings().all()
    return api_rows([dict(row) for row in rows])


@router.get("/governanca/sessoes")
def listar_sessoes(user: AuthUser = Depends(require_profiles("ADM"))) -> list[dict[str, object]]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(f"SELECT * FROM {schema}.vw_midway_governanca_sessoes_ativas ORDER BY expira_em DESC")
        ).mappings().all()
    return api_rows([dict(row) for row in rows])


@router.get("/governanca/execucoes/tipos")
def listar_tipos_execucao(user: AuthUser = Depends(require_profiles("ADM", "GESTOR"))) -> list[dict[str, object]]:
    return api_rows(
        [
            {
                "tipo_lote": tipo_lote,
                "titulo": config["titulo"],
                "descricao": config["descricao"],
                "comando": f"run.bat {tipo_lote}",
            }
            for tipo_lote, config in EXECUCOES_PERMITIDAS.items()
        ]
    )


@router.get("/governanca/execucoes")
def listar_execucoes(user: AuthUser = Depends(require_profiles("ADM", "GESTOR", "AUDITOR"))) -> list[dict[str, object]]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(
                f"""
                SELECT id_lote, anomes, tipo_lote, status_lote, origem, parametros,
                       iniciado_em, finalizado_em, criado_por, mensagem
                FROM {schema}.midway_execucao_lote
                ORDER BY iniciado_em DESC
                LIMIT 100
                """
            )
        ).mappings().all()
    return api_rows([dict(row) for row in rows])


@router.post("/governanca/execucoes")
def iniciar_execucao(
    payload: ExecucaoRequest,
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR")),
) -> dict[str, object]:
    tipo_lote = payload.tipo_lote.strip().lower()
    anomes = payload.anomes.strip()
    if tipo_lote not in EXECUCOES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Tipo de processamento inválido.")
    if len(anomes) != 6 or not anomes.isdigit():
        raise HTTPException(status_code=400, detail="ANOMES deve ter 6 dígitos.")

    schema = _schema()
    engine = create_postgres_engine()
    
    with engine.begin() as con:
        active = con.execute(
            text(f"SELECT id_lote, tipo_lote FROM {schema}.midway_execucao_lote WHERE status_lote IN ('ABERTO', 'PROCESSANDO')")
        ).mappings().first()
        if active:
            raise HTTPException(
                status_code=409,
                detail=f"Já existe um processamento em andamento ({active['tipo_lote']}). Aguarde a conclusão ou cancele a execução ativa."
            )

        id_lote = str(uuid4())
        parametros = payload.parametros or {}
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_execucao_lote (
                    id_lote, anomes, tipo_lote, status_lote, origem, parametros, criado_por, mensagem
                )
                VALUES (
                    :id_lote, :anomes, :tipo_lote, 'ABERTO', 'api_admin',
                    CAST(:parametros AS jsonb), :criado_por, :mensagem
                )
                """
            ),
            {
                "id_lote": id_lote,
                "anomes": anomes,
                "tipo_lote": tipo_lote,
                "parametros": json.dumps(parametros, ensure_ascii=False),
                "criado_por": user.login,
                "mensagem": f"Solicitado pela Administração: {EXECUCOES_PERMITIDAS[tipo_lote]['titulo']}.",
            },
        )

    forcar = bool(payload.forcar)
    thread = threading.Thread(target=_executar_lote_background, args=(id_lote, tipo_lote, anomes, forcar), daemon=True)
    thread.start()
    audit_event(
        "EXECUCAO_LOTE_SOLICITADA",
        "midway_execucao_lote",
        id_lote,
        user.login,
        {"tipo_lote": tipo_lote, "anomes": anomes},
    )
    return {"id_lote": id_lote, "status": "ABERTO", "tipo_lote": tipo_lote}


@router.post("/governanca/execucoes/{id_lote}/cancelar")
def cancelar_execucao(
    id_lote: str,
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR")),
) -> dict[str, object]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        row = con.execute(
            text(f"SELECT id_lote, status_lote FROM {schema}.midway_execucao_lote WHERE id_lote = :id_lote"),
            {"id_lote": id_lote}
        ).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Execução não encontrada.")
        if row["status_lote"] not in ("ABERTO", "PROCESSANDO"):
            raise HTTPException(status_code=400, detail="Apenas execuções ativas (ABERTO ou PROCESSANDO) podem ser canceladas.")

        con.execute(
            text(f"UPDATE {schema}.midway_execucao_lote SET status_lote = 'CANCELADO', mensagem = 'Cancelado pelo usuário.', finalizado_em = now() WHERE id_lote = :id_lote"),
            {"id_lote": id_lote}
        )
    audit_event("EXECUCAO_LOTE_CANCELADA", "midway_execucao_lote", id_lote, user.login, {})
    return {"id_lote": id_lote, "status": "CANCELADO"}


@router.get("/governanca/alteracoes")
def listar_alteracoes(user: AuthUser = Depends(get_current_user)) -> list[dict[str, object]]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(f"SELECT * FROM {schema}.vw_midway_governanca_alteracoes ORDER BY criado_em DESC LIMIT 300")
        ).mappings().all()
    return api_rows([dict(row) for row in rows])


@router.post("/governanca/alteracoes")
def registrar_alteracao(
    payload: AlteracaoRequest,
    user: AuthUser = Depends(get_current_user),
) -> dict[str, object]:
    import json

    schema = _schema()
    id_alteracao = str(uuid4())
    engine = create_postgres_engine()
    
    check_fechamento(schema, engine, payload.anomes)
    
    with engine.begin() as con:
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_alteracao_registro (
                    id_alteracao, anomes, modulo, entidade, id_entidade, tipo_alteracao,
                    status_alteracao, antes, depois, justificativa, solicitado_por
                )
                VALUES (
                    :id_alteracao, :anomes, :modulo, :entidade, :id_entidade, :tipo_alteracao,
                    :status_alteracao, CAST(:antes AS jsonb), CAST(:depois AS jsonb),
                    :justificativa, :solicitado_por
                )
                """
            ),
            {
                "id_alteracao": id_alteracao,
                "anomes": payload.anomes,
                "modulo": payload.modulo,
                "entidade": payload.entidade,
                "id_entidade": payload.id_entidade,
                "tipo_alteracao": payload.tipo_alteracao,
                "status_alteracao": payload.status_alteracao,
                "antes": json.dumps(payload.antes or {}, ensure_ascii=False),
                "depois": json.dumps(payload.depois or {}, ensure_ascii=False),
                "justificativa": payload.justificativa,
                "solicitado_por": user.login,
            },
        )
    audit_event("ALTERACAO_REGISTRADA", payload.entidade, payload.id_entidade, user.login, {"id_alteracao": id_alteracao})
    return {"id_alteracao": id_alteracao, "status": "registrada"}


def _decidir_alteracao(
    id_alteracao: str,
    payload: DecisaoAlteracaoRequest,
    novo_status: str,
    tipo_evento: str,
    user: AuthUser,
) -> dict[str, object]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        row = con.execute(
            text(
                f"""
                SELECT id_alteracao, anomes, entidade, id_entidade, solicitado_por, status_alteracao
                FROM {schema}.midway_alteracao_registro
                WHERE id_alteracao = :id_alteracao
                """
            ),
            {"id_alteracao": id_alteracao},
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Alteração não encontrada.")
            
        check_fechamento(schema, engine, str(row["anomes"]))
        
        if row["status_alteracao"] != "PENDENTE":
            raise HTTPException(status_code=409, detail="Apenas alterações pendentes podem ser decididas.")
        if row["solicitado_por"] == user.login:
            raise HTTPException(status_code=403, detail="O solicitante não pode aprovar ou rejeitar a própria alteração.")

        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_alteracao_registro
                SET status_alteracao = :status_alteracao,
                    aprovado_por = :aprovado_por,
                    atualizado_em = now(),
                    justificativa = justificativa || E'\n\nDecisão gestor: ' || :justificativa
                WHERE id_alteracao = :id_alteracao
                """
            ),
            {
                "id_alteracao": id_alteracao,
                "status_alteracao": novo_status,
                "aprovado_por": user.login,
                "justificativa": payload.justificativa,
            },
        )

    audit_event(
        tipo_evento,
        str(row["entidade"]),
        str(row["id_entidade"] or id_alteracao),
        user.login,
        {
            "id_alteracao": id_alteracao,
            "status": novo_status,
            "justificativa": payload.justificativa,
        },
    )
    return {"id_alteracao": id_alteracao, "status": novo_status}


@router.patch("/governanca/alteracoes/{id_alteracao}/aprovar")
def aprovar_alteracao(
    id_alteracao: str,
    payload: DecisaoAlteracaoRequest,
    user: AuthUser = Depends(require_profiles("GESTOR", "ADM")),
) -> dict[str, object]:
    return _decidir_alteracao(id_alteracao, payload, "APROVADA", "PROPOSTA_APROVADA", user)


@router.patch("/governanca/alteracoes/{id_alteracao}/rejeitar")
def rejeitar_alteracao(
    id_alteracao: str,
    payload: DecisaoAlteracaoRequest,
    user: AuthUser = Depends(require_profiles("GESTOR", "ADM")),
) -> dict[str, object]:
    return _decidir_alteracao(id_alteracao, payload, "REJEITADA", "PROPOSTA_REJEITADA", user)


@router.get("/governanca/auditoria")
def listar_auditoria(user: AuthUser = Depends(get_current_user)) -> list[dict[str, object]]:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.connect() as con:
        rows = con.execute(
            text(f"SELECT * FROM {schema}.vw_midway_governanca_auditoria LIMIT 300")
        ).mappings().all()
    return api_rows([dict(row) for row in rows])


@router.get("/governanca/verificacoes")
def verificacoes(user: AuthUser = Depends(get_current_user)) -> dict[str, object]:
    validation = validate_postgres()
    return api_row(
        {
            "database_ok": validation.ok,
            "schema": validation.current_schema,
            "tables": validation.table_count,
            "views": validation.view_count,
            "parameters": validation.parameter_count,
            "missing_tables": validation.missing_tables,
            "missing_views": validation.missing_views,
            "missing_parameters": validation.missing_parameters,
        }
    )


@router.get("/governanca/sql/scripts")
def listar_sql_scripts(user: AuthUser = Depends(require_profiles("ADM", "GESTOR"))) -> list[dict[str, object]]:
    scripts_dir = Path("SQL/postgres/ddcq")
    scripts = []
    for path in sorted(scripts_dir.glob("*.sql")):
        scripts.append(
            {
                "nome": path.name,
                "caminho": str(path).replace("\\", "/"),
                "tamanho": path.stat().st_size,
                "alterado_em": path.stat().st_mtime,
            }
        )
    return api_rows(scripts)

def check_fechamento(schema: str, engine, anomes: str):
    with engine.begin() as con:
        # Garante a tabela
        con.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {schema}.midway_mes_apuracao (
            anomes VARCHAR(6) PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'ABERTO',
            fechado_em TIMESTAMP,
            fechado_por VARCHAR(100)
        );
        """))
        res = con.execute(text(f"SELECT status FROM {schema}.midway_mes_apuracao WHERE anomes = :anomes"), {"anomes": anomes}).scalar()
        if res == 'FECHADO':
            raise HTTPException(status_code=403, detail=f"O mês {anomes} já está FECHADO. Nenhuma alteração permitida.")

def get_fechamento_status(schema: str, engine, anomes: str):
    with engine.begin() as con:
        con.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {schema}.midway_mes_apuracao (
            anomes VARCHAR(6) PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'ABERTO',
            fechado_em TIMESTAMP,
            fechado_por VARCHAR(100)
        );
        """))
        res = con.execute(text(f"SELECT status FROM {schema}.midway_mes_apuracao WHERE anomes = :anomes"), {"anomes": anomes}).scalar()
        return res or 'ABERTO'

@router.get("/governanca/fechamento")
def obter_status_fechamento(anomes: str | None = Query(None, description="Anomes (ex: 202606)"), user: AuthUser = Depends(get_current_user)):
    from dotenv import load_dotenv
    load_dotenv(override=True)
    target_anomes = anomes or os.getenv("ANOMES", "202607")
    engine = create_postgres_engine()
    schema = _schema()
    status = get_fechamento_status(schema, engine, target_anomes)
    return {"anomes": target_anomes, "status": status}

@router.post("/governanca/fechamento")
def fechar_mes(anomes: str | None = Query(None, description="Anomes (ex: 202606)"), user: AuthUser = Depends(get_current_user)):
    target_anomes = anomes or os.getenv("ANOMES", "202606")
    engine = create_postgres_engine()
    schema = _schema()
    
    with engine.begin() as con:
        con.execute(text(f"""
        INSERT INTO {schema}.midway_mes_apuracao (anomes, status, fechado_em, fechado_por)
        VALUES (:anomes, 'FECHADO', CURRENT_TIMESTAMP, :user)
        ON CONFLICT (anomes) DO UPDATE SET 
            status = 'FECHADO',
            fechado_em = CURRENT_TIMESTAMP,
            fechado_por = :user
        """), {"anomes": target_anomes, "user": user.login})
    
    # Atualizar o arquivo .env
    from pathlib import Path
    env_path = Path("D:/MIDWAY/.env")
    novo_anomes = target_anomes
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        
        # Incrementar mês
        ano = int(target_anomes[:4])
        mes = int(target_anomes[4:])
        if mes == 12:
            novo_anomes = f"{ano + 1}01"
        else:
            novo_anomes = f"{ano}{mes + 1:02d}"
            
        new_content = []
        for line in content.splitlines():
            if line.startswith("ANOMES="):
                new_content.append(f"ANOMES={novo_anomes}")
            else:
                new_content.append(line)
        env_path.write_text("\n".join(new_content) + "\n", encoding="utf-8")
        
    os.environ["ANOMES"] = novo_anomes
    audit_event("MES_FECHADO", "midway_mes_apuracao", target_anomes, user.login, {"novo_anomes": novo_anomes})
    return {"status": "FECHADO", "novo_anomes": novo_anomes}

class ReaberturaRequest(BaseModel):
    justificativa: str

@router.post("/governanca/fechamento/{anomes}/reabrir")
def reabrir_mes(anomes: str, payload: ReaberturaRequest, user: AuthUser = Depends(get_current_user)):
    if user.funcao != "ADMIN":
        raise HTTPException(status_code=403, detail="Apenas administradores podem reabrir o mês.")
        
    engine = create_postgres_engine()
    schema = _schema()
    
    with engine.begin() as con:
        con.execute(text(f"""
        UPDATE {schema}.midway_mes_apuracao
        SET status = 'ABERTO',
            fechado_em = NULL,
            fechado_por = NULL
        WHERE anomes = :anomes
        """), {"anomes": anomes})
        
    # Atualizar o arquivo .env de volta para o anomes reaberto
    from pathlib import Path
    env_path = Path("D:/MIDWAY/.env")
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        new_content = []
        for line in content.splitlines():
            if line.startswith("ANOMES="):
                new_content.append(f"ANOMES={anomes}")
            else:
                new_content.append(line)
        env_path.write_text("\n".join(new_content) + "\n", encoding="utf-8")
        
    os.environ["ANOMES"] = anomes
    audit_event("MES_REABERTO", "midway_mes_apuracao", anomes, user.login, {"justificativa": payload.justificativa})
    return {"status": "ABERTO", "anomes": anomes}

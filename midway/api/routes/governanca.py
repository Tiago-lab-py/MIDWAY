from __future__ import annotations

import secrets
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
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


class LoginRequest(BaseModel):
    email: str
    senha: str


class UsuarioCreateRequest(BaseModel):
    nome: str
    email: str
    perfil: str
    senha: str


class ResetSenhaConfirmRequest(BaseModel):
    codigo: str
    nova_senha: str
    justificativa: str


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


@router.get("/governanca/usuarios")
def listar_usuarios(
    user: AuthUser = Depends(require_profiles("ADM", "GESTOR")),
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
    perfil = payload.perfil.upper().strip()
    email = _normalize_email(payload.email)
    if perfil not in {"ADM", "GESTOR", "ANALISTA"}:
        raise HTTPException(status_code=400, detail="Perfil inválido.")
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


@router.post("/governanca/reset-senha/{id_reset}/confirmar")
def confirmar_reset_senha(
    id_reset: str,
    payload: ResetSenhaConfirmRequest,
    user: AuthUser = Depends(require_profiles("ADM")),
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
                "confirmado_por": user.login,
                "justificativa": payload.justificativa.strip(),
                "id_reset": id_reset,
            },
        )

    audit_event(
        "RESET_SENHA_CONFIRMADO",
        "midway_usuario",
        str(reset_row["id_usuario"]),
        user.login,
        {"email": reset_row.get("email") or reset_row["login"], "perfil": reset_row["perfil"], "id_reset": id_reset},
    )
    return {"status": "confirmado", "id_reset": id_reset, "login": reset_row.get("email") or reset_row["login"]}


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
                SELECT id_alteracao, entidade, id_entidade, solicitado_por, status_alteracao
                FROM {schema}.midway_alteracao_registro
                WHERE id_alteracao = :id_alteracao
                """
            ),
            {"id_alteracao": id_alteracao},
        ).mappings().first()

        if not row:
            raise HTTPException(status_code=404, detail="Alteração não encontrada.")
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

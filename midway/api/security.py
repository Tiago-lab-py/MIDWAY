from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from midway.db.postgres import create_postgres_engine, get_config

PBKDF2_ITERATIONS = int(os.getenv("MIDWAY_AUTH_PBKDF2_ITERATIONS", "390000"))
SESSION_HOURS = int(os.getenv("MIDWAY_AUTH_SESSION_HOURS", "8"))


@dataclass(frozen=True)
class AuthUser:
    id_usuario: str
    login: str
    nome: str
    email: str | None
    perfil: str


def _schema() -> str:
    schema = get_config().schema
    if not schema.replace("_", "").isalnum():
        raise RuntimeError("Schema PostgreSQL inválido.")
    return schema


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return (
        "pbkdf2_sha256"
        f"${PBKDF2_ITERATIONS}"
        f"${base64.b64encode(salt).decode('ascii')}"
        f"${base64.b64encode(digest).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(digest_b64.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(id_usuario: str, request: Request | None = None) -> dict[str, object]:
    schema = _schema()
    raw_token = secrets.token_urlsafe(48)
    token_hash = hash_token(raw_token)
    id_sessao = str(uuid4())
    expira_em = datetime.now() + timedelta(hours=SESSION_HOURS)
    ip_origem = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None

    engine = create_postgres_engine()
    with engine.begin() as con:
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_sessao (
                    id_sessao, id_usuario, token_hash, ip_origem, user_agent, expira_em, ultimo_uso_em
                )
                VALUES (
                    :id_sessao, :id_usuario, :token_hash, :ip_origem, :user_agent, :expira_em, now()
                )
                """
            ),
            {
                "id_sessao": id_sessao,
                "id_usuario": id_usuario,
                "token_hash": token_hash,
                "ip_origem": ip_origem,
                "user_agent": user_agent,
                "expira_em": expira_em,
            },
        )

    return {
        "access_token": raw_token,
        "token_type": "bearer",
        "expires_at": expira_em.isoformat(),
    }


def revoke_session(token: str) -> None:
    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        con.execute(
            text(
                f"""
                UPDATE {schema}.midway_sessao
                SET revogado_em = now()
                WHERE token_hash = :token_hash
                  AND revogado_em IS NULL
                """
            ),
            {"token_hash": hash_token(token)},
        )


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticação ausente.")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    token = _bearer_token(authorization)
    schema = _schema()
    engine = create_postgres_engine()
    try:
        with engine.begin() as con:
            row = con.execute(
                text(
                    f"""
                    SELECT
                        u.id_usuario,
                        u.login,
                        u.nome,
                        u.email,
                        u.perfil
                    FROM {schema}.midway_sessao s
                    JOIN {schema}.midway_usuario u
                        ON u.id_usuario = s.id_usuario
                    WHERE s.token_hash = :token_hash
                      AND s.revogado_em IS NULL
                      AND s.expira_em > now()
                      AND u.status_usuario = 'ATIVO'
                    """
                ),
                {"token_hash": hash_token(token)},
            ).mappings().first()

            if not row:
                raise HTTPException(status_code=401, detail="Sessão expirada ou inválida.")

            con.execute(
                text(
                    f"""
                    UPDATE {schema}.midway_sessao
                    SET ultimo_uso_em = now()
                    WHERE token_hash = :token_hash
                    """
                ),
                {"token_hash": hash_token(token)},
            )
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL indisponível para validar a sessão. Inicie o banco local e faça login novamente.",
        ) from exc

    return AuthUser(
        id_usuario=str(row["id_usuario"]),
        login=str(row["login"]),
        nome=str(row["nome"]),
        email=row["email"],
        perfil=str(row["perfil"]),
    )


def require_profiles(*profiles: str):
    allowed = set(profiles)

    def dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if user.perfil not in allowed:
            raise HTTPException(status_code=403, detail="Perfil sem permissão para esta ação.")
        return user

    return dependency


def audit_event(
    tipo_evento: str,
    entidade: str,
    id_entidade: str | None,
    usuario: str,
    detalhe: dict[str, object] | None = None,
    anomes: str | None = None,
) -> None:
    import json

    schema = _schema()
    engine = create_postgres_engine()
    with engine.begin() as con:
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_auditoria_evento (
                    id_evento, anomes, tipo_evento, entidade, id_entidade, usuario, detalhe
                )
                VALUES (
                    :id_evento, :anomes, :tipo_evento, :entidade, :id_entidade, :usuario,
                    CAST(:detalhe AS jsonb)
                )
                """
            ),
            {
                "id_evento": str(uuid4()),
                "anomes": anomes,
                "tipo_evento": tipo_evento,
                "entidade": entidade,
                "id_entidade": id_entidade,
                "usuario": usuario,
                "detalhe": json.dumps(detalhe or {}, ensure_ascii=False),
            },
        )

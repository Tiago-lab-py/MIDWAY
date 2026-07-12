from __future__ import annotations

import os
import secrets
import sys
from uuid import uuid4

from sqlalchemy import text

from midway.api.security import hash_password
from midway.db.postgres import create_postgres_engine, get_config


def main() -> None:
    config = get_config()
    schema = config.schema
    if not schema.replace("_", "").isalnum():
        raise RuntimeError("Schema PostgreSQL inválido.")

    email = os.getenv("MIDWAY_BOOTSTRAP_EMAIL", "admin@midway.local").strip()
    login = email.lower()
    nome = os.getenv("MIDWAY_BOOTSTRAP_NOME", "Administrador MIDWAY").strip()
    password = os.getenv("MIDWAY_BOOTSTRAP_PASSWORD")
    generated = False
    if not password:
        password = secrets.token_urlsafe(18)
        generated = True

    if len(password) < 12:
        print("Senha inicial deve ter no mínimo 12 caracteres.")
        sys.exit(1)

    engine = create_postgres_engine(config)
    with engine.begin() as con:
        total_users = con.execute(text(f"SELECT COUNT(*) FROM {schema}.midway_usuario")).scalar_one()
        existing = con.execute(
            text(f"SELECT id_usuario FROM {schema}.midway_usuario WHERE lower(coalesce(email, login)) = :email"),
            {"email": login},
        ).scalar_one_or_none()

        if existing:
            print(f"Usuario '{login}' ja existe. Nenhuma alteracao realizada.")
            return

        id_usuario = str(uuid4())
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_usuario (
                    id_usuario, login, nome, email, perfil, senha_hash, criado_por, atualizado_por
                )
                VALUES (
                    :id_usuario, :login, :nome, :email, 'ADM', :senha_hash, 'BOOTSTRAP', 'BOOTSTRAP'
                )
                """
            ),
            {
                "id_usuario": id_usuario,
                "login": login,
                "nome": nome,
                "email": email,
                "senha_hash": hash_password(password),
            },
        )

        id_evento = str(uuid4())
        con.execute(
            text(
                f"""
                INSERT INTO {schema}.midway_auditoria_evento (
                    id_evento, tipo_evento, entidade, id_entidade, usuario, detalhe
                )
                VALUES (
                    :id_evento, 'BOOTSTRAP_ADMIN', 'midway_usuario',
                    :id_usuario, 'BOOTSTRAP', '{{"perfil":"ADM"}}'::jsonb
                )
                """
            ),
            {"id_evento": id_evento, "id_usuario": id_usuario},
        )

    print("BOOTSTRAP ADMIN MIDWAY")
    print(f"Usuarios anteriores: {total_users}")
    print(f"E-mail/login: {login}")
    print(f"Perfil: ADM")
    if generated:
        print(f"Senha temporaria gerada: {password}")
        print("Troque esta senha apos o primeiro acesso.")
    else:
        print("Senha definida por MIDWAY_BOOTSTRAP_PASSWORD.")


if __name__ == "__main__":
    main()

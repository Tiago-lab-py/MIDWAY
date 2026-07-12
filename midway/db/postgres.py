from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Iterable

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


load_dotenv()

DEFAULT_SCHEMA = "ddcq"

REQUIRED_TABLES = [
    "midway_ajuste_iqs",
    "midway_alteracao_registro",
    "midway_auditoria_evento",
    "midway_autorizacao_executiva",
    "midway_execucao_lote",
    "midway_exportacao_iqs",
    "midway_fila_tecnica",
    "midway_iqs_geracao",
    "midway_iqs_geracao_modelo",
    "midway_parametro",
    "midway_reset_senha",
    "midway_sessao",
    "midway_usuario",
    "midway_v7_anomalia",
    "midway_v7_decisao",
    "midway_v7_evidencia",
    "midway_v7_sugestao",
]

REQUIRED_VIEWS = [
    "vw_midway_governanca_alteracoes",
    "vw_midway_governanca_auditoria",
    "vw_midway_governanca_reset_senha",
    "vw_midway_governanca_sessoes_ativas",
    "vw_midway_governanca_usuarios",
    "vw_midway_iqs_geracao",
    "vw_midway_iqs_geracao_modelo",
    "vw_midway_9282_ajustes_auto",
    "vw_midway_9282_auditoria",
    "vw_midway_9282_fila_tecnica",
    "vw_midway_9282_painel",
]

REQUIRED_PARAMETERS = [
    "exportacao.iqs.apenas_aprovados",
    "midway.env",
    "midway.schema",
    "midway.v7.anomalias.fonte",
    "midway.version.target",
    "regra.9282.automatico",
    "regra.9282.manual",
]


@dataclass(frozen=True)
class PostgresConfig:
    database_url: str
    schema: str = DEFAULT_SCHEMA
    environment: str = "local"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    current_user: str
    current_database: str
    current_schema: str
    missing_tables: list[str]
    missing_views: list[str]
    missing_parameters: list[str]
    table_count: int
    view_count: int
    parameter_count: int


def get_config() -> PostgresConfig:
    database_url = os.getenv("MIDWAY_DATABASE_URL") or os.getenv("DB_URL")
    if not database_url:
        raise RuntimeError(
            "Configure MIDWAY_DATABASE_URL no .env. "
            "Exemplo: postgresql://midway_app:senha@localhost:5432/midway"
        )

    return PostgresConfig(
        database_url=database_url,
        schema=os.getenv("MIDWAY_DB_SCHEMA", DEFAULT_SCHEMA).strip() or DEFAULT_SCHEMA,
        environment=os.getenv("MIDWAY_ENV", "local").strip() or "local",
    )


def create_postgres_engine(config: PostgresConfig | None = None) -> Engine:
    config = config or get_config()
    return create_engine(config.database_url, pool_pre_ping=True)


def _rows_to_list(rows: Iterable[tuple]) -> list[str]:
    return [str(row[0]) for row in rows]


def validate_postgres(config: PostgresConfig | None = None) -> ValidationResult:
    config = config or get_config()
    engine = create_postgres_engine(config)

    with engine.connect() as con:
        identity = con.execute(
            text("SELECT current_user, current_database(), current_schema()")
        ).one()

        tables = _rows_to_list(
            con.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = :schema
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                    """
                ),
                {"schema": config.schema},
            ).fetchall()
        )

        views = _rows_to_list(
            con.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.views
                    WHERE table_schema = :schema
                    ORDER BY table_name
                    """
                ),
                {"schema": config.schema},
            ).fetchall()
        )

        parameters = _rows_to_list(
            con.execute(
                text(
                    f"""
                    SELECT chave
                    FROM {config.schema}.midway_parametro
                    ORDER BY chave
                    """
                )
            ).fetchall()
            if "midway_parametro" in tables
            else []
        )

    missing_tables = sorted(set(REQUIRED_TABLES) - set(tables))
    missing_views = sorted(set(REQUIRED_VIEWS) - set(views))
    missing_parameters = sorted(set(REQUIRED_PARAMETERS) - set(parameters))
    ok = (
        not missing_tables
        and not missing_views
        and not missing_parameters
        and str(identity[2]) == config.schema
    )

    return ValidationResult(
        ok=ok,
        current_user=str(identity[0]),
        current_database=str(identity[1]),
        current_schema=str(identity[2]),
        missing_tables=missing_tables,
        missing_views=missing_views,
        missing_parameters=missing_parameters,
        table_count=len(tables),
        view_count=len(views),
        parameter_count=len(parameters),
    )


def print_validation(result: ValidationResult) -> None:
    print("VALIDACAO POSTGRESQL MIDWAY")
    print(f"Status: {'OK' if result.ok else 'ERRO'}")
    print(f"Usuario: {result.current_user}")
    print(f"Database: {result.current_database}")
    print(f"Schema atual: {result.current_schema}")
    print(f"Tabelas encontradas: {result.table_count}")
    print(f"Views encontradas: {result.view_count}")
    print(f"Parametros encontrados: {result.parameter_count}")

    if result.missing_tables:
        print("Tabelas ausentes:")
        for table in result.missing_tables:
            print(f"  - {table}")

    if result.missing_views:
        print("Views ausentes:")
        for view in result.missing_views:
            print(f"  - {view}")

    if result.missing_parameters:
        print("Parametros ausentes:")
        for parameter in result.missing_parameters:
            print(f"  - {parameter}")


def main() -> None:
    try:
        config = get_config()
        print(f"Ambiente: {config.environment}")
        print(f"Schema esperado: {config.schema}")
        result = validate_postgres(config)
        print_validation(result)
        if not result.ok:
            sys.exit(1)
    except Exception as error:
        print("VALIDACAO POSTGRESQL MIDWAY")
        print("Status: ERRO")
        print(f"Falha: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()

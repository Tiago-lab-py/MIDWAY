from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from midway.db.postgres import validate_postgres

router = APIRouter(prefix="/api", tags=["health"])


def _version() -> str:
    version_path = Path("VERSION")
    if version_path.exists():
        return version_path.read_text(encoding="utf-8").strip()
    return "dev"


@router.get("/health")
def health() -> dict[str, object]:
    database: dict[str, object]
    try:
        validation = validate_postgres()
        database = {
            "status": "ok" if validation.ok else "warning",
            "schema": validation.current_schema,
            "tables": validation.table_count,
            "views": validation.view_count,
            "parameters": validation.parameter_count,
            "missing_tables": validation.missing_tables,
            "missing_views": validation.missing_views,
            "missing_parameters": validation.missing_parameters,
        }
    except Exception as error:
        database = {
            "status": "error",
            "message": str(error),
        }

    return {
        "status": "ok",
        "app": "MIDWAY API",
        "version": _version(),
        "database": database,
    }

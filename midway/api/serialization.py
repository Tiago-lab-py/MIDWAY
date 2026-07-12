from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


def api_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: api_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [api_value(item) for item in value]
    return value


def api_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: api_value(value) for key, value in row.items()}


def api_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [api_row(row) for row in rows]

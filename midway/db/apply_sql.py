from __future__ import annotations

import sys
from pathlib import Path

from midway.db.postgres import create_postgres_engine, get_config

SQL_DIR = Path("SQL/postgres/ddcq")


def apply_sql(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    engine = create_postgres_engine(get_config())
    with engine.begin() as con:
        con.exec_driver_sql(sql)
    print(f"SQL aplicado: {path}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python -m midway.db.apply_sql <arquivo.sql|all>")
        sys.exit(1)

    target = sys.argv[1]
    if target.lower() == "all":
        paths = sorted(SQL_DIR.glob("*.sql"))
    else:
        path = Path(target)
        if not path.exists():
            path = SQL_DIR / target
        paths = [path]

    for path in paths:
        if not path.exists():
            print(f"Arquivo SQL nao encontrado: {path}")
            sys.exit(1)
        apply_sql(path)


if __name__ == "__main__":
    main()

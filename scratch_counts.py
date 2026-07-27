import sys
import os

sys.path.append("D:\\MIDWAY")
from midway.db.postgres import create_postgres_engine
from sqlalchemy import text
from midway.v7.anomaly_repository import _schema

schema = _schema()
engine = create_postgres_engine()
with engine.connect() as con:
    rows = con.execute(text(f"SELECT codigo_modulo, count(*) FROM {schema}.midway_propostas_tratamento GROUP BY codigo_modulo")).fetchall()
    for r in rows:
        print(f"{r[0]}: {r[1]}")

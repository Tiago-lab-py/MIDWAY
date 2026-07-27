from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from midway.api.routes import anomalias, executivo_9282, exportacoes, governanca, health, iqs, produto, qualidade


def create_app() -> FastAPI:
    app = FastAPI(
        title="MIDWAY API",
        version="7.1.0",
        description="API operacional do MIDWAY para React, PostgreSQL ddcq e processamentos IQS.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(governanca.router)
    app.include_router(executivo_9282.router)
    app.include_router(iqs.router)
    app.include_router(qualidade.router)
    app.include_router(anomalias.router)
    app.include_router(produto.router)
    app.include_router(exportacoes.router)

    @app.on_event("startup")
    def limpar_lotes_travados():
        from sqlalchemy import text
        from midway.db.postgres import create_postgres_engine
        from midway.api.routes.governanca import _schema
        schema = _schema()
        engine = create_postgres_engine()
        try:
            with engine.begin() as con:
                con.execute(
                    text(
                        f"""
                        UPDATE {schema}.midway_execucao_lote
                        SET status_lote = 'ERRO',
                            mensagem = 'Execução cancelada devido ao reinício da aplicação.'
                        WHERE status_lote IN ('ABERTO', 'PROCESSANDO')
                        """
                    )
                )
        except Exception:
            pass

    return app


app = create_app()

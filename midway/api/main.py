from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from midway.api.routes import anomalias, executivo_9282, governanca, health, iqs, qualidade


def create_app() -> FastAPI:
    app = FastAPI(
        title="MIDWAY API",
        version="7.0.0",
        description="API operacional do MIDWAY para React, PostgreSQL ddcq e processamentos IQS.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
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
    return app


app = create_app()

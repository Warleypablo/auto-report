from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import cases, health, rankings
from config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vitrine de Cases API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    app.include_router(rankings.router, prefix="/api")
    return app


app = create_app()

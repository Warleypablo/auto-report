from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import cases, health, internal, rankings
from config import get_settings
from logging_config import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vitrine de Cases API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    app.include_router(rankings.router, prefix="/api")
    app.include_router(internal.router, prefix="/internal")
    return app


app = create_app()

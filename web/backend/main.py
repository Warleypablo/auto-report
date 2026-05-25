import socket
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import anyio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import cases, health, internal, rankings
from api.auth import router as auth_router
from api.gestor import router as gestor_router
from app_settings import get_settings
from logging_config import setup_logging

# Timeout HARD em qualquer chamada socket (HTTP, DB, etc) — evita hangs eternos
# em Google APIs que travam sem responder. 90s é folgado pro caso normal.
socket.setdefaulttimeout(90)


def _cleanup_stale_jobs() -> None:
    """On startup: mark jobs stuck in 'running' or 'pending' for >10 min as error."""
    try:
        from db import SessionLocal
        from models import ReportJob
        from models.report_job import JobStatus
        from sqlalchemy import select, text

        with SessionLocal() as session:
            stale = session.execute(
                select(ReportJob).where(
                    ReportJob.status.in_([JobStatus.RUNNING, JobStatus.PENDING]),
                    ReportJob.created_at < text("NOW() - INTERVAL '10 minutes'"),
                )
            ).scalars().all()
            for job in stale:
                job.status = JobStatus.ERROR
                job.erro = f"Timeout no startup — job estava em {job.status.value} há mais de 10 min"
                job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
            if stale:
                session.commit()
    except Exception:
        pass  # Don't fail startup because of this


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # Aumenta o threadpool do AnyIO (usado pelo FastAPI para endpoints sync)
    # default é 40 — polling de muitos jobs simultâneos pode saturar e causar 502
    anyio.to_thread.current_default_thread_limiter().total_tokens = 100
    _cleanup_stale_jobs()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Vitrine de Cases API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    app.include_router(rankings.router, prefix="/api")
    app.include_router(internal.router, prefix="/internal")
    app.include_router(auth_router)
    app.include_router(gestor_router, prefix="/gestor")
    return app


app = create_app()

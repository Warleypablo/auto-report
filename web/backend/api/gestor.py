from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from api.auth import require_admin, require_auth
from db import get_session
from models import Cliente, ReportJob, Usuario, UsuarioCliente
from models.report_job import JobStatus
from schemas import (
    AssignClientesRequest,
    ClienteGestorItem,
    ClientesGestorResponse,
    CreateUsuarioRequest,
    JobStatusResponse,
    TriggerRequest,
    TriggerResponse,
    UsuarioListItem,
    UsuarioResponse,
    UsuariosListResponse,
)
from sqlalchemy import func

router = APIRouter()

_MES_RE = __import__("re").compile(r"^\d{4}-\d{2}$")


# ── Helpers ────────────────────────────────────────────────────────────────

def _job_to_response(job: ReportJob) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        mes=job.mes,
        status=job.status.value,
        slides_url=job.slides_url,
        erro=job.erro,
        created_at=job.created_at,
        finished_at=job.finished_at,
        cliente_slug=job.cliente.slug,
        cliente_nome=job.cliente.nome,
    )


def _mark_stale_running_jobs(session: Session) -> None:
    """Mark jobs stuck in 'running' for more than 10 minutes as error."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    session.execute(
        update(ReportJob)
        .where(ReportJob.status == JobStatus.RUNNING, ReportJob.created_at < cutoff)
        .values(
            status=JobStatus.ERROR,
            erro="Timeout: job ficou em running por mais de 10 minutos",
            finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
    )
    session.commit()


# ── GET /gestor/clientes ───────────────────────────────────────────────────

@router.get("/clientes", response_model=ClientesGestorResponse)
def list_clientes(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClientesGestorResponse:
    stmt = (
        select(Cliente)
        .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
        .where(UsuarioCliente.usuario_id == user.id)
        .order_by(Cliente.nome.asc())
    )
    clientes = session.execute(stmt).scalars().all()
    return ClientesGestorResponse(
        items=[
            ClienteGestorItem(id=c.id, slug=c.slug, nome=c.nome, categoria=c.categoria.value)
            for c in clientes
        ]
    )


# ── POST /gestor/reports/trigger ───────────────────────────────────────────

@router.post("/reports/trigger", response_model=TriggerResponse)
def trigger_report(
    body: TriggerRequest,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> TriggerResponse:
    if not _MES_RE.match(body.mes):
        raise HTTPException(status_code=400, detail="mes deve ser YYYY-MM")

    # Verify user has access to this client
    cliente = session.execute(
        select(Cliente)
        .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
        .where(
            Cliente.slug == body.slug,
            UsuarioCliente.usuario_id == user.id,
        )
    ).scalar_one_or_none()
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado ou sem acesso")

    # Mark any stale running jobs before checking for duplicates
    _mark_stale_running_jobs(session)

    # Prevent duplicate running job for same client
    running = session.execute(
        select(ReportJob).where(
            ReportJob.cliente_id == cliente.id,
            ReportJob.status == JobStatus.RUNNING,
        )
    ).scalar_one_or_none()
    if running is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Já existe um job em andamento para este cliente (job_id={running.id})",
        )

    job = ReportJob(
        usuario_id=user.id,
        cliente_id=cliente.id,
        mes=body.mes,
        status=JobStatus.PENDING,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    job_id = job.id
    cliente_slug = cliente.slug
    cliente_nome = cliente.nome
    mes = body.mes

    def _run():
        from db import SessionLocal
        from services.report_slides import gerar_slides

        with SessionLocal() as bg_session:
            bg_job = bg_session.get(ReportJob, job_id)
            if bg_job is None:
                return
            bg_job.status = JobStatus.RUNNING
            bg_session.commit()

        try:
            url = gerar_slides(slug=cliente_slug, nome_cliente=cliente_nome, mes=mes)
            with SessionLocal() as bg_session:
                bg_job = bg_session.get(ReportJob, job_id)
                if bg_job:
                    bg_job.status = JobStatus.DONE
                    bg_job.slides_url = url
                    bg_job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    bg_session.commit()
        except Exception as exc:
            with SessionLocal() as bg_session:
                bg_job = bg_session.get(ReportJob, job_id)
                if bg_job:
                    bg_job.status = JobStatus.ERROR
                    bg_job.erro = str(exc)[:500]
                    bg_job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    bg_session.commit()

    threading.Thread(target=_run, daemon=True).start()
    return TriggerResponse(job_id=job.id)


# ── GET /gestor/reports/{job_id} ───────────────────────────────────────────

@router.get("/reports/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: uuid.UUID,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> JobStatusResponse:
    job = session.execute(
        select(ReportJob)
        .options(selectinload(ReportJob.cliente))
        .where(ReportJob.id == job_id, ReportJob.usuario_id == user.id)
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    return _job_to_response(job)


# ── GET /gestor/reports ────────────────────────────────────────────────────

@router.get("/reports", response_model=list[JobStatusResponse])
def list_jobs(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
    slug: str | None = Query(default=None),
) -> list[JobStatusResponse]:
    stmt = (
        select(ReportJob)
        .options(selectinload(ReportJob.cliente))
        .where(ReportJob.usuario_id == user.id)
        .order_by(ReportJob.created_at.desc())
        .limit(50)
    )
    if slug:
        stmt = stmt.join(Cliente, Cliente.id == ReportJob.cliente_id).where(Cliente.slug == slug)
    jobs = session.execute(stmt).scalars().all()
    return [_job_to_response(j) for j in jobs]

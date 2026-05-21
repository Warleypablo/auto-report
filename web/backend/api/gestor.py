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


# ── Admin: GET /gestor/admin/usuarios ─────────────────────────────────────

@router.get("/admin/usuarios", response_model=UsuariosListResponse)
def admin_list_usuarios(
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UsuariosListResponse:
    stmt = (
        select(
            Usuario,
            func.count(UsuarioCliente.cliente_id).label("n_clientes"),
        )
        .outerjoin(UsuarioCliente, UsuarioCliente.usuario_id == Usuario.id)
        .group_by(Usuario.id)
        .order_by(Usuario.nome.asc())
    )
    rows = session.execute(stmt).all()
    return UsuariosListResponse(
        items=[
            UsuarioListItem(
                id=u.id,
                email=u.email,
                nome=u.nome,
                is_admin=u.is_admin,
                ativo=u.ativo,
                n_clientes=n,
            )
            for u, n in rows
        ]
    )


# ── Admin: POST /gestor/admin/usuarios ────────────────────────────────────

@router.post("/admin/usuarios", response_model=UsuarioResponse, status_code=201)
def admin_create_usuario(
    body: CreateUsuarioRequest,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UsuarioResponse:
    from api.auth import hash_password
    from sqlalchemy import select as sa_select

    existing = session.execute(
        sa_select(Usuario).where(Usuario.email == body.email)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    user = Usuario(
        email=body.email,
        nome=body.nome,
        senha_hash=hash_password(body.senha),
        is_admin=body.is_admin,
        ativo=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return UsuarioResponse(id=user.id, email=user.email, nome=user.nome, is_admin=user.is_admin)


# ── Admin: DELETE /gestor/admin/usuarios/{id} (deactivate) ────────────────

@router.delete("/admin/usuarios/{usuario_id}", status_code=204)
def admin_deactivate_usuario(
    usuario_id: uuid.UUID,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    user = session.get(Usuario, usuario_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    user.ativo = False
    session.commit()


# ── Admin: GET /gestor/admin/usuarios/{id}/clientes ───────────────────────

@router.get("/admin/usuarios/{usuario_id}/clientes", response_model=ClientesGestorResponse)
def admin_get_usuario_clientes(
    usuario_id: uuid.UUID,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ClientesGestorResponse:
    stmt = (
        select(Cliente)
        .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
        .where(UsuarioCliente.usuario_id == usuario_id)
        .order_by(Cliente.nome.asc())
    )
    clientes = session.execute(stmt).scalars().all()
    return ClientesGestorResponse(
        items=[ClienteGestorItem(id=c.id, slug=c.slug, nome=c.nome, categoria=c.categoria.value) for c in clientes]
    )


# ── Admin: POST /gestor/admin/usuarios/{id}/clientes ──────────────────────

@router.post("/admin/usuarios/{usuario_id}/clientes", status_code=204)
def admin_assign_clientes(
    usuario_id: uuid.UUID,
    body: AssignClientesRequest,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    user = session.get(Usuario, usuario_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    existing = {
        uc.cliente_id
        for uc in session.execute(
            select(UsuarioCliente).where(UsuarioCliente.usuario_id == usuario_id)
        ).scalars().all()
    }

    for cid in body.cliente_ids:
        if cid not in existing:
            session.add(UsuarioCliente(usuario_id=usuario_id, cliente_id=cid))

    session.commit()


# ── Admin: DELETE /gestor/admin/usuarios/{id}/clientes/{cliente_id} ───────

@router.delete("/admin/usuarios/{usuario_id}/clientes/{cliente_id}", status_code=204)
def admin_remove_cliente(
    usuario_id: uuid.UUID,
    cliente_id: uuid.UUID,
    admin: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    uc = session.execute(
        select(UsuarioCliente).where(
            UsuarioCliente.usuario_id == usuario_id,
            UsuarioCliente.cliente_id == cliente_id,
        )
    ).scalar_one_or_none()
    if uc:
        session.delete(uc)
        session.commit()

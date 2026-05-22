from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import distinct, select, text, update
from sqlalchemy.orm import Session, selectinload

from api.auth import require_admin, require_auth
from db import get_session
from models import Cliente, ReportJob, Usuario, UsuarioCliente
from models.cliente import Categoria as CatEnum
from models.report_job import JobStatus
from etl.cliente_publico import slugify
from schemas import (
    AssignClientesRequest,
    ClienteCreateRequest,
    ClienteDetalheItem,
    ClienteEditRequest,
    ClienteGestorItem,
    ClienteMetricasItem,
    ClientesGestorResponse,
    CreateUsuarioRequest,
    GestorRenameRequest,
    GestorRenameResponse,
    GestoresResponse,
    JobStatusResponse,
    MetricasDashboardResponse,
    TriggerRequest,
    TriggerResponse,
    UsuarioListItem,
    UsuarioResponse,
    UsuariosListResponse,
)
from sqlalchemy import func

router = APIRouter()

_MES_RE = __import__("re").compile(r"^\d{4}-\d{2}$")

_LOWERCASE_PT = {"da", "de", "do", "das", "dos", "e", "von", "van", "del"}


def normalize_gestor_name(name: str) -> str:
    """Normaliza capitalização: 'gabriel taufner' → 'Gabriel Taufner', preserva 'da/de/do'."""
    name = " ".join(name.split())
    if not name:
        return name
    result = []
    for i, word in enumerate(name.split()):
        if i > 0 and word.lower() in _LOWERCASE_PT:
            result.append(word.lower())
        else:
            result.append(word[0].upper() + word[1:].lower() if word else "")
    return " ".join(result)


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
    """Mark jobs stuck in 'running' for more than 30 minutes as error."""
    stale = session.execute(
        select(ReportJob).where(
            ReportJob.status == JobStatus.RUNNING,
            ReportJob.created_at < text("NOW() - INTERVAL '30 minutes'"),
        )
    ).scalars().all()
    for job in stale:
        job.status = JobStatus.ERROR
        job.erro = "Timeout: job ficou em running por mais de 30 minutos"
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if stale:
        session.commit()


# ── GET /gestor/clientes ───────────────────────────────────────────────────

@router.get("/clientes", response_model=ClientesGestorResponse)
def list_clientes(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClientesGestorResponse:
    if user.is_admin:
        stmt = select(Cliente).where(Cliente.ativo == True).order_by(Cliente.nome.asc())
    else:
        stmt = (
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(UsuarioCliente.usuario_id == user.id, Cliente.ativo == True)
            .order_by(Cliente.nome.asc())
        )
    clientes = session.execute(stmt).scalars().all()
    return ClientesGestorResponse(
        items=[ClienteGestorItem.model_validate(c) for c in clientes]
    )


# ── POST /gestor/clientes ─────────────────────────────────────────────────────

@router.post("/clientes", response_model=ClienteDetalheItem, status_code=201)
def create_cliente(
    body: ClienteCreateRequest,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClienteDetalheItem:
    slug = slugify(body.nome)
    if session.execute(select(Cliente).where(Cliente.slug == slug)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Já existe um cliente com o slug '{slug}'")

    cliente = Cliente(
        slug=slug,
        nome=body.nome,
        categoria=CatEnum(body.categoria),
        gestor=normalize_gestor_name(body.gestor) if body.gestor else None,
        id_google_ads=body.id_google_ads,
        id_meta_ads=body.id_meta_ads,
        id_ga4=body.id_ga4,
        painel_url=body.painel_url,
        pasta_url=body.pasta_url,
        ativo=True,
        destaque=False,
        publicar_vitrine=False,
    )
    session.add(cliente)
    session.flush()

    if not user.is_admin:
        session.add(UsuarioCliente(usuario_id=user.id, cliente_id=cliente.id))

    session.commit()
    session.refresh(cliente)
    return ClienteDetalheItem.model_validate(cliente)


# ── GET /gestor/gestores ───────────────────────────────────────────────────────

@router.get("/gestores", response_model=GestoresResponse)
def list_gestores(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> GestoresResponse:
    from sqlalchemy import distinct
    if user.is_admin:
        stmt = (
            select(distinct(Cliente.gestor))
            .where(Cliente.gestor.isnot(None), Cliente.ativo == True)
            .order_by(Cliente.gestor)
        )
    else:
        stmt = (
            select(distinct(Cliente.gestor))
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(
                UsuarioCliente.usuario_id == user.id,
                Cliente.gestor.isnot(None),
                Cliente.ativo == True,
            )
            .order_by(Cliente.gestor)
        )
    gestores = [row[0] for row in session.execute(stmt).all()]
    return GestoresResponse(items=gestores)


# ── PATCH /gestor/gestores — renomear gestor em lote ─────────────────────────

@router.patch("/gestores", response_model=GestorRenameResponse)
def rename_gestor(
    body: GestorRenameRequest,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> GestorRenameResponse:
    para_normalizado = normalize_gestor_name(body.para)
    if not para_normalizado:
        raise HTTPException(status_code=422, detail="O novo nome não pode ser vazio")

    if user.is_admin:
        stmt = (
            update(Cliente)
            .where(Cliente.gestor == body.de, Cliente.ativo == True)
            .values(gestor=para_normalizado)
        )
    else:
        cliente_ids = session.execute(
            select(UsuarioCliente.cliente_id).where(UsuarioCliente.usuario_id == user.id)
        ).scalars().all()
        stmt = (
            update(Cliente)
            .where(Cliente.gestor == body.de, Cliente.id.in_(cliente_ids), Cliente.ativo == True)
            .values(gestor=para_normalizado)
        )

    result = session.execute(stmt)
    session.commit()
    return GestorRenameResponse(de=body.de, para=para_normalizado, atualizados=result.rowcount)


# ── POST /gestor/gestores/normalizar — corrige capitalização em lote ──────────

@router.post("/gestores/normalizar")
def normalizar_gestores(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    if user.is_admin:
        nomes = session.execute(
            select(distinct(Cliente.gestor)).where(Cliente.gestor.isnot(None), Cliente.ativo == True)
        ).scalars().all()
    else:
        cliente_ids_scoped = session.execute(
            select(UsuarioCliente.cliente_id).where(UsuarioCliente.usuario_id == user.id)
        ).scalars().all()
        nomes = session.execute(
            select(distinct(Cliente.gestor))
            .where(Cliente.gestor.isnot(None), Cliente.id.in_(cliente_ids_scoped), Cliente.ativo == True)
        ).scalars().all()

    mapeamento = []
    for nome in nomes:
        normalizado = normalize_gestor_name(nome)
        if normalizado == nome:
            continue
        if user.is_admin:
            r = session.execute(
                update(Cliente).where(Cliente.gestor == nome, Cliente.ativo == True).values(gestor=normalizado)
            )
        else:
            r = session.execute(
                update(Cliente)
                .where(Cliente.gestor == nome, Cliente.id.in_(cliente_ids_scoped), Cliente.ativo == True)
                .values(gestor=normalizado)
            )
        mapeamento.append({"de": nome, "para": normalizado, "atualizados": r.rowcount})

    session.commit()
    return {"mapeamento": mapeamento, "nomes_alterados": len(mapeamento)}


# ── PATCH /gestor/clientes/{cliente_id} ───────────────────────────────────

@router.patch("/clientes/{cliente_id}", response_model=ClienteDetalheItem)
def update_cliente(
    cliente_id: uuid.UUID,
    body: ClienteEditRequest,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClienteDetalheItem:
    if user.is_admin:
        cliente = session.get(Cliente, cliente_id)
    else:
        cliente = session.execute(
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(Cliente.id == cliente_id, UsuarioCliente.usuario_id == user.id)
        ).scalar_one_or_none()

    if cliente is None or not cliente.ativo:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "categoria" and value is not None:
            value = CatEnum(value)
        elif field == "gestor" and value is not None:
            value = normalize_gestor_name(value)
        setattr(cliente, field, value)

    session.commit()
    session.refresh(cliente)
    return ClienteDetalheItem.model_validate(cliente)


# ── DELETE /gestor/clientes/{cliente_id} (soft delete) ────────────────────

@router.delete("/clientes/{cliente_id}", status_code=204)
def deactivate_cliente(
    cliente_id: uuid.UUID,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> None:
    if user.is_admin:
        cliente = session.get(Cliente, cliente_id)
    else:
        cliente = session.execute(
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(Cliente.id == cliente_id, UsuarioCliente.usuario_id == user.id)
        ).scalar_one_or_none()

    if cliente is None or not cliente.ativo:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    cliente.ativo = False
    session.commit()


# ── POST /gestor/reports/trigger ───────────────────────────────────────────

@router.post("/reports/trigger", response_model=TriggerResponse)
def trigger_report(
    body: TriggerRequest,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> TriggerResponse:
    if not _MES_RE.match(body.mes):
        raise HTTPException(status_code=400, detail="mes deve ser YYYY-MM")

    # Verify user has access to this client (admins can access all clients)
    if user.is_admin:
        cliente = session.execute(
            select(Cliente).where(Cliente.slug == body.slug)
        ).scalar_one_or_none()
    else:
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
    stmt = select(ReportJob).options(selectinload(ReportJob.cliente)).where(ReportJob.id == job_id)
    if not user.is_admin:
        stmt = stmt.where(ReportJob.usuario_id == user.id)
    job = session.execute(stmt).scalar_one_or_none()
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
        items=[ClienteGestorItem.model_validate(c) for c in clientes]
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


# ── GET /gestor/metricas ───────────────────────────────────────────────────

@router.get("/metricas", response_model=MetricasDashboardResponse)
def get_metricas_dashboard(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> MetricasDashboardResponse:
    from models.snapshot import Snapshot
    from sqlalchemy import desc

    # Resolve client list for this user
    if user.is_admin:
        clientes = session.execute(
            select(Cliente).where(Cliente.ativo == True).order_by(Cliente.nome)
        ).scalars().all()
    else:
        clientes = session.execute(
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(UsuarioCliente.usuario_id == user.id, Cliente.ativo == True)
            .order_by(Cliente.nome)
        ).scalars().all()

    cliente_ids = [c.id for c in clientes]
    if not cliente_ids:
        return MetricasDashboardResponse(
            items=[], total_faturamento=0, total_investimento=0,
            media_roas=None, total_leads=0, total_vendas=0,
        )

    # Latest MENSAL snapshot per client via a subquery
    sub = (
        select(
            Snapshot.cliente_id,
            func.max(Snapshot.periodo_fim).label("max_fim"),
        )
        .where(
            Snapshot.cliente_id.in_(cliente_ids),
            Snapshot.frequencia == "MENSAL",
        )
        .group_by(Snapshot.cliente_id)
        .subquery()
    )

    snapshots = session.execute(
        select(Snapshot).join(
            sub,
            (Snapshot.cliente_id == sub.c.cliente_id)
            & (Snapshot.periodo_fim == sub.c.max_fim),
        )
    ).scalars().all()

    snap_by_client = {s.cliente_id: s for s in snapshots}

    items: list[ClienteMetricasItem] = []
    for c in clientes:
        s = snap_by_client.get(c.id)
        items.append(ClienteMetricasItem(
            slug=c.slug,
            nome=c.nome,
            categoria=c.categoria.value,
            periodo_inicio=str(s.periodo_inicio) if s else None,
            periodo_fim=str(s.periodo_fim) if s else None,
            faturamento=float(s.faturamento) if s and s.faturamento is not None else None,
            investimento=float(s.investimento) if s and s.investimento is not None else None,
            roas=float(s.roas) if s and s.roas is not None else None,
            cpa=float(s.cpa) if s and s.cpa is not None else None,
            leads=s.leads if s else None,
            vendas=s.vendas if s else None,
            faturamento_var_pct=float(s.faturamento_var_pct) if s and s.faturamento_var_pct is not None else None,
            roas_var_pct=float(s.roas_var_pct) if s and s.roas_var_pct is not None else None,
        ))

    with_data = [i for i in items if i.faturamento is not None or i.investimento is not None]
    roas_vals = [i.roas for i in items if i.roas is not None]

    return MetricasDashboardResponse(
        items=items,
        total_faturamento=sum(i.faturamento for i in with_data if i.faturamento),
        total_investimento=sum(i.investimento for i in with_data if i.investimento),
        media_roas=sum(roas_vals) / len(roas_vals) if roas_vals else None,
        total_leads=sum(i.leads for i in items if i.leads),
        total_vendas=sum(i.vendas for i in items if i.vendas),
    )

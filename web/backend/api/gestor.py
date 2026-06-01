from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import distinct, or_, select, text, update
from sqlalchemy.orm import Session, selectinload

from api.auth import require_admin, require_auth
from db import get_session, SessionLocal
from app_settings import Settings, get_settings
from models import AdInsight, Cliente, GestorCadastrado, Insight, ReportJob, Usuario, UsuarioCliente
from models.snapshot import Snapshot
from models.snapshot import Frequencia as SnapFrequencia
from models.cliente import Categoria as CatEnum
from models.criativo import Criativo, CriativoThumb, ThumbStatus
from services.criativos import agregar_criativos
from services.clickup_match import responsavel_performance
from models.report_job import JobStatus
from etl.cliente_publico import slugify
from schemas import (
    BackfillJobStatusResponse,
    BackfillRequest,
    BackfillResponse,
    CoberturaClienteItem,
    CoberturaResponse,
    CriativosResponse,
    AssignClientesRequest,
    ClienteCreateRequest,
    CupClienteInfo,
    ClienteDetalheItem,
    ClienteEditRequest,
    ClienteGestorItem,
    ClienteMetricasItem,
    ClientesGestorResponse,
    CreateUsuarioRequest,
    GestorCadastradoCreate,
    GestorCadastradoItem,
    GestorCadastradosResponse,
    GestorRenameRequest,
    GestorRenameResponse,
    GestoresResponse,
    InteligenciaAlerta,
    InteligenciaGenerateResponse,
    InteligenciaResponse,
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
_log = logging.getLogger(__name__)

# Limita quantos jobs de geração de relatório rodam simultaneamente por processo.
# Previne esgotamento do pool de conexões do DB e sobrecarga de threads/quotas Google
# com muitos clientes disparados de uma vez. Ajustável via env MAX_CONCURRENT_REPORT_JOBS.
_MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_REPORT_JOBS", "1"))
_JOB_SEMAPHORE = threading.BoundedSemaphore(_MAX_CONCURRENT_JOBS)

# Estado em memória para jobs de backfill histórico.
# Suficiente para uso esporádico por admins — não persiste entre reinicializações.
_backfill_jobs: dict[str, dict] = {}

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
        frequencia=job.frequencia,
        status=job.status.value,
        slides_url=job.slides_url,
        erro=job.erro,
        created_at=job.created_at,
        finished_at=job.finished_at,
        cliente_slug=job.cliente.slug,
        cliente_nome=job.cliente.nome,
    )


def _mark_stale_jobs(session: Session) -> None:
    """Mark jobs stuck in 'running' or 'pending' for more than 10 minutes as error."""
    stale = session.execute(
        select(ReportJob).where(
            ReportJob.status.in_([JobStatus.RUNNING, JobStatus.PENDING]),
            ReportJob.created_at < text("NOW() - INTERVAL '10 minutes'"),
        )
    ).scalars().all()
    for job in stale:
        job.status = JobStatus.ERROR
        job.erro = f"Timeout: job ficou em {job.status.value} por mais de 10 minutos"
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if stale:
        session.commit()


# ── GET /gestor/clickup/sem-vinculo ────────────────────────────────────────
# Lista clientes ativos sem cup_task_id + sugestões automáticas por similaridade
# de nome com staging.cup_clientes. Usado pela UI admin de vinculação manual.

@router.get("/clickup/sem-vinculo", status_code=200)
def listar_clientes_sem_vinculo_cup(
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    rows = session.execute(
        text("""
            SELECT
                c.id::text   AS cliente_id,
                c.nome       AS cliente_nome,
                c.categoria  AS cliente_categoria,
                c.gestor     AS cliente_gestor,
                COALESCE(
                    (
                        SELECT json_agg(s ORDER BY s.score DESC)
                        FROM (
                            SELECT
                                cc.task_id,
                                cc.nome,
                                cc.responsavel,
                                CASE
                                    WHEN LOWER(TRIM(cc.nome)) = LOWER(TRIM(c.nome)) THEN 1.0
                                    WHEN LOWER(TRIM(cc.nome)) LIKE LOWER(TRIM(c.nome)) || '%' THEN 0.85
                                    WHEN LOWER(TRIM(c.nome)) LIKE LOWER(TRIM(cc.nome)) || '%' THEN 0.80
                                    WHEN LOWER(cc.nome) LIKE '%' || LOWER(TRIM(c.nome)) || '%' THEN 0.7
                                    WHEN LOWER(c.nome) LIKE '%' || LOWER(TRIM(cc.nome)) || '%' THEN 0.65
                                    ELSE 0.0
                                END AS score
                            FROM staging.cup_clientes cc
                            WHERE LOWER(cc.nome) LIKE '%' || LOWER(SPLIT_PART(TRIM(c.nome), ' ', 1)) || '%'
                               OR LOWER(c.nome) LIKE '%' || LOWER(SPLIT_PART(TRIM(cc.nome), ' ', 1)) || '%'
                            ORDER BY score DESC
                            LIMIT 5
                        ) s
                        WHERE s.score > 0
                    ),
                    '[]'::json
                ) AS sugestoes
            FROM clientes c
            WHERE c.ativo = true
              AND c.cup_task_id IS NULL
            ORDER BY c.nome ASC
        """)
    ).mappings().all()

    return {
        "total": len(rows),
        "items": [dict(r) for r in rows],
    }


# ── GET /gestor/clickup/tasks ──────────────────────────────────────────────
# Busca tasks no ClickUp por nome (substring case-insensitive) — autocomplete

@router.get("/clickup/tasks", status_code=200)
def buscar_clickup_tasks(
    q: str = Query("", min_length=0, max_length=120),
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    q = q.strip()
    if len(q) < 2:
        return {"items": []}

    rows = session.execute(
        text("""
            SELECT
                cc.task_id,
                cc.nome,
                cc.responsavel,
                cc.status,
                -- já está vinculado a algum cliente?
                (SELECT json_build_object('id', cl.id::text, 'nome', cl.nome)
                 FROM clientes cl WHERE cl.cup_task_id = cc.task_id LIMIT 1
                ) AS vinculado_a
            FROM staging.cup_clientes cc
            WHERE LOWER(cc.nome) LIKE '%' || LOWER(:q) || '%'
            ORDER BY cc.nome ASC
            LIMIT 20
        """),
        {"q": q},
    ).mappings().all()

    return {"items": [dict(r) for r in rows]}


# ── PATCH /gestor/clientes/{id}/cup-task ───────────────────────────────────
# Vincula (ou desvincula com null) um cliente a um task_id do ClickUp.

class _CupTaskPatch(BaseModel):
    cup_task_id: str | None = None


@router.patch("/clientes/{cliente_id}/cup-task", status_code=200)
def patch_cup_task(
    cliente_id: uuid.UUID,
    body: _CupTaskPatch,
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    cliente = session.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    novo_task_id = (body.cup_task_id or "").strip() or None

    if novo_task_id:
        # Validar que o task_id existe em staging.cup_clientes
        exists = session.execute(
            text("SELECT 1 FROM staging.cup_clientes WHERE task_id = :tid LIMIT 1"),
            {"tid": novo_task_id},
        ).scalar()
        if not exists:
            raise HTTPException(
                status_code=422,
                detail=f"task_id '{novo_task_id}' não existe em staging.cup_clientes",
            )

        # Validar que ninguém mais está vinculado a esse task_id
        outro = session.execute(
            select(Cliente).where(
                Cliente.cup_task_id == novo_task_id,
                Cliente.id != cliente_id,
            )
        ).scalar_one_or_none()
        if outro is not None:
            raise HTTPException(
                status_code=409,
                detail=f"task_id '{novo_task_id}' já está vinculado ao cliente '{outro.nome}'",
            )

    cliente.cup_task_id = novo_task_id
    session.commit()
    return {"cliente_id": str(cliente.id), "cup_task_id": cliente.cup_task_id}


# ── POST /gestor/clickup/automatch ─────────────────────────────────────────
# Vincula clientes sem cup_task_id por PROXIMIDADE de nome (services.clickup_match):
# - auto-aplica só matches de alta confiança e sem ambiguidade (classificar == "auto")
# - os de confiança média viram sugestões (ambiguos) para revisão manual
# - dry_run=true (default) retorna proposta sem aplicar

from collections import defaultdict


@router.post("/clickup/automatch", status_code=200)
def automatch_clickup(
    dry_run: bool = Query(True),
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    from services.clickup_match import melhores_candidatos, classificar

    cup_rows = [
        {"task_id": r["task_id"], "nome": r["nome"]}
        for r in session.execute(
            text("SELECT task_id, nome FROM staging.cup_clientes "
                 "WHERE nome IS NOT NULL AND TRIM(nome) <> ''")
        ).mappings().all()
    ]

    clientes = session.execute(
        select(Cliente)
        .where(Cliente.cup_task_id.is_(None), Cliente.ativo == True)  # noqa: E712
        .order_by(Cliente.nome.asc())
    ).scalars().all()

    matches: list[dict] = []
    ambiguos: list[dict] = []
    sem_candidato: list[dict] = []

    for c in clientes:
        cands = melhores_candidatos(c.nome, cup_rows, k=5)
        cls = classificar(cands)
        if cls == "auto":
            sc, tid, cup_nome = cands[0]
            matches.append({
                "cliente_id": str(c.id), "cliente_nome": c.nome,
                "task_id": tid, "cup_nome": cup_nome, "score": round(sc, 3),
            })
        elif cls == "sugestao":
            ambiguos.append({
                "cliente_id": str(c.id), "cliente_nome": c.nome,
                "candidatos": [
                    {"task_id": tid, "nome": nome, "score": round(sc, 3)}
                    for sc, tid, nome in cands if sc >= 0.70
                ],
            })
        else:
            sem_candidato.append({"cliente_id": str(c.id), "cliente_nome": c.nome})

    aplicados = 0
    if not dry_run and matches:
        usados_nesta_run: set[str] = set()
        for m in matches:
            # Evita que dois clientes da mesma execução reivindiquem o mesmo
            # task_id (autoflush=False não materializa o UPDATE anterior antes
            # do próximo SELECT, então o ja_usado abaixo não o veria).
            if m["task_id"] in usados_nesta_run:
                continue
            ja_usado = session.execute(
                select(Cliente.id).where(Cliente.cup_task_id == m["task_id"])
            ).scalar_one_or_none()
            if ja_usado is not None:
                continue
            session.execute(
                update(Cliente)
                .where(Cliente.id == uuid.UUID(m["cliente_id"]))
                .values(cup_task_id=m["task_id"])
            )
            usados_nesta_run.add(m["task_id"])
            aplicados += 1
        session.commit()
        _log.info("automatch: aplicados=%d (de %d propostos)", aplicados, len(matches))

    return {
        "dry_run": dry_run,
        "matches": matches,
        "aplicados": aplicados,
        "ambiguos": ambiguos,
        "sem_candidato": sem_candidato,
        "stats": {
            "total_clientes_sem_vinculo": len(clientes),
            "matches_propostos": len(matches),
            "ambiguos": len(ambiguos),
            "sem_candidato": len(sem_candidato),
        },
    }


# ── POST /gestor/clientes/sync-gestores ────────────────────────────────────
# Atribui clientes.gestor = staging.cup_clientes.responsavel para todos os
# clientes vinculados (cup_task_id IS NOT NULL). Útil quando há rotatividade
# de gestores no ClickUp e queremos refletir no sistema.

@router.post("/clientes/sync-gestores", status_code=200)
def sync_gestores_from_clickup(
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    """Atribui clientes.gestor = responsável do contrato 'Performance' vigente
    no ClickUp, seguindo o vínculo cup_task_id.

    Caminho do dado (relaciona por cup_task_id, NÃO por nome):
      clientes.cup_task_id  →  staging.cup_contratos.id_task
                               ↓ filtra servico ILIKE '%performance%'
                               ↓ contrato vigente mais recente (services.clickup_match)
                               responsavel → normalize_gestor_name → clientes.gestor
    """
    rows = session.execute(
        text("""
            SELECT c.id::text AS cliente_id, c.gestor, c.gestor_travado,
                   ct.servico, ct.status, ct.responsavel, ct.data_inicio
            FROM clientes c
            JOIN staging.cup_contratos ct ON ct.id_task = c.cup_task_id
            WHERE c.ativo = true AND c.cup_task_id IS NOT NULL
        """)
    ).mappings().all()

    # Agrupa contratos por cliente
    por_cliente: dict[str, dict] = {}
    for r in rows:
        ent = por_cliente.setdefault(r["cliente_id"], {
            "gestor_atual": r["gestor"],
            "gestor_travado": r["gestor_travado"],
            "contratos": [],
        })
        ent["contratos"].append({
            "servico": r["servico"], "status": r["status"],
            "responsavel": r["responsavel"], "data_inicio": r["data_inicio"],
        })

    com_vinculo = session.execute(
        text("SELECT COUNT(*) FROM clientes WHERE ativo = true AND cup_task_id IS NOT NULL")
    ).scalar() or 0
    total_ativos = session.execute(
        text("SELECT COUNT(*) FROM clientes WHERE ativo = true")
    ).scalar() or 0

    com_contrato_performance = 0
    com_responsavel = 0
    a_atualizar = 0
    atualizados = 0

    for cliente_id, ent in por_cliente.items():
        tem_perf = any(
            "performance" in (c.get("servico") or "").lower()
            for c in ent["contratos"]
        )
        if tem_perf:
            com_contrato_performance += 1
        resp_bruto = responsavel_performance(ent["contratos"])
        if resp_bruto is None:
            continue
        com_responsavel += 1
        novo = normalize_gestor_name(resp_bruto)
        if ent["gestor_travado"]:
            continue
        if ent["gestor_atual"] == novo:
            continue
        a_atualizar += 1
        # Guarda extra no WHERE: protege contra um PATCH concorrente que trave
        # o gestor entre o SELECT inicial e este UPDATE (janela TOCTOU).
        res = session.execute(
            update(Cliente)
            .where(Cliente.id == uuid.UUID(cliente_id),
                   Cliente.gestor_travado == False)  # noqa: E712
            .values(gestor=novo, atualizado_em=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        atualizados += res.rowcount

    session.commit()

    _log.info(
        "sync-gestores: atualizados=%d a_atualizar=%d total_ativos=%d com_vinculo=%d "
        "com_contrato_performance=%d com_responsavel=%d",
        atualizados, a_atualizar, total_ativos, com_vinculo,
        com_contrato_performance, com_responsavel,
    )

    return {
        "atualizados": atualizados,
        "a_atualizar": a_atualizar,
        "total_ativos": total_ativos,
        "com_vinculo": com_vinculo,
        "com_match_nome": com_vinculo,  # alias retrocompatível (deprecado)
        "com_contrato_performance": com_contrato_performance,
        "com_responsavel": com_responsavel,
    }


# ── GET /gestor/clientes ───────────────────────────────────────────────────

@router.get("/clientes", response_model=ClientesGestorResponse)
def list_clientes(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClientesGestorResponse:
    from sqlalchemy import text

    # "Ativo p/ report" é data-driven: além do flag, inclui quem investiu algo
    # nos últimos 30 dias (clientes que estão gastando mas estão marcados inativos
    # no cadastro). Evita esconder cliente que está rodando mídia.
    limite_30d = date.today() - timedelta(days=30)
    com_spend_recente = (
        select(distinct(AdInsight.cliente_id))
        .where(AdInsight.dia >= limite_30d, AdInsight.investimento > 0)
    )
    ativo_ou_investiu = or_(Cliente.ativo == True, Cliente.id.in_(com_spend_recente))

    if user.is_admin:
        stmt = select(Cliente).where(ativo_ou_investiu).order_by(Cliente.nome.asc())
    else:
        stmt = (
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(UsuarioCliente.usuario_id == user.id, ativo_ou_investiu)
            .order_by(Cliente.nome.asc())
        )
    clientes = session.execute(stmt).scalars().all()

    # Busca dados do ClickUp via join direto pelos cup_task_ids dos clientes
    cup_map: dict = {}
    if clientes:
        rows = session.execute(
            text("""
                SELECT
                    cc.task_id,
                    cc.status, cc.responsavel, cc.responsavel_geral,
                    cc.vendedor, cc.squad, cc.segmento, cc.cluster,
                    cc.status_conta, cc.motivo_cancelamento,
                    ct.servico  AS contrato_servico,
                    ct.produto  AS contrato_produto,
                    ct.plano    AS contrato_plano,
                    ct.valorr   AS contrato_valor_recorrente,
                    ct.status   AS contrato_status
                FROM clientes c
                JOIN staging.cup_clientes cc ON cc.task_id = c.cup_task_id
                LEFT JOIN LATERAL (
                    SELECT * FROM staging.cup_contratos
                    WHERE id_task = cc.task_id
                    ORDER BY data_inicio DESC NULLS LAST
                    LIMIT 1
                ) ct ON TRUE
            """)
        ).mappings().all()
        cup_map = {r["task_id"]: dict(r) for r in rows}

    items = []
    for c in clientes:
        data = ClienteGestorItem.model_validate(c)
        if c.cup_task_id and c.cup_task_id in cup_map:
            data.cup = CupClienteInfo.model_validate(cup_map[c.cup_task_id])
        items.append(data)

    return ClientesGestorResponse(items=items)


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
    """Lista gestores OFICIAIS (gestores_cadastrados) que têm pelo menos 1
    cliente ATIVO no ClickUp.

    Filtra dropdown por whitelist + status comercial:
    - Nome aparece SOMENTE se constar em gestores_cadastrados
    - Cliente associado precisa ter clientes.ativo=true E
      staging.cup_clientes.status='ativo'

    Variantes/abreviações em clientes.gestor que não batem exato com
    gestores_cadastrados.nome ficam fora — limpeza por dependência
    da whitelist, não por código fuzzy.
    """
    exists_clause = """
        EXISTS (
            SELECT 1
            FROM clientes c
            JOIN staging.cup_clientes cc ON cc.task_id = c.cup_task_id
            {extra_join}
            WHERE c.gestor = gc.nome
              AND c.ativo = true
              AND LOWER(COALESCE(cc.status, '')) = 'ativo'
              {extra_where}
        )
    """

    if user.is_admin:
        sql = (
            "SELECT gc.nome FROM gestores_cadastrados gc WHERE "
            + exists_clause.format(extra_join="", extra_where="")
            + " ORDER BY gc.nome"
        )
        params: dict = {}
    else:
        sql = (
            "SELECT gc.nome FROM gestores_cadastrados gc WHERE "
            + exists_clause.format(
                extra_join="JOIN usuario_clientes uc ON uc.cliente_id = c.id",
                extra_where="AND uc.usuario_id = :uid",
            )
            + " ORDER BY gc.nome"
        )
        params = {"uid": str(user.id)}

    rows = session.execute(text(sql), params).all()
    gestores = [r[0] for r in rows]
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


# ── GET /gestor/gestores-cadastrados ─────────────────────────────────────────

@router.get("/gestores-cadastrados", response_model=GestorCadastradosResponse)
def list_gestores_cadastrados(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> GestorCadastradosResponse:
    items = session.execute(
        select(GestorCadastrado).order_by(GestorCadastrado.nome)
    ).scalars().all()
    return GestorCadastradosResponse(items=[GestorCadastradoItem.model_validate(g) for g in items])


# ── POST /gestor/gestores-cadastrados ─────────────────────────────────────────

@router.post("/gestores-cadastrados", response_model=GestorCadastradoItem, status_code=201)
def create_gestor_cadastrado(
    body: GestorCadastradoCreate,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> GestorCadastradoItem:
    nome = normalize_gestor_name(body.nome)
    if not nome:
        raise HTTPException(status_code=422, detail="Nome não pode ser vazio")
    if session.execute(select(GestorCadastrado).where(GestorCadastrado.nome == nome)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Gestor '{nome}' já cadastrado")
    g = GestorCadastrado(nome=nome, squad=body.squad.strip() if body.squad else None)
    session.add(g)
    session.commit()
    session.refresh(g)
    return GestorCadastradoItem.model_validate(g)


# ── POST /gestor/admin/cleanup-gestores ──────────────────────────────────────
# Roteiro automatizado para sanear a lista do dropdown:
#   1. Normaliza capitalização em clientes.gestor (alexandre → Alexandre)
#   2. Cadastra em gestores_cadastrados todos os nomes distintos que sobram
#      em clientes.gestor (apenas dos clientes com cliente ativo + cup status
#      ativo) — ON CONFLICT DO NOTHING, então é idempotente.
#   3. Retorna relatório do que foi alterado.
#
# Não tenta desambiguar variantes (Alexander vs Alexandre Costa) — isso é
# trabalho de revisão manual via PATCH /gestor/gestores.

@router.post("/admin/cleanup-gestores", status_code=200)
def cleanup_gestores(
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    # ── 1. Normaliza capitalização em clientes.gestor ────────────────────
    nomes_brutos = session.execute(
        select(distinct(Cliente.gestor)).where(
            Cliente.gestor.isnot(None), Cliente.ativo == True  # noqa: E712
        )
    ).scalars().all()

    normalizacoes: list[dict] = []
    for nome in nomes_brutos:
        normalizado = normalize_gestor_name(nome)
        if normalizado == nome:
            continue
        r = session.execute(
            update(Cliente)
            .where(Cliente.gestor == nome, Cliente.ativo == True)  # noqa: E712
            .values(gestor=normalizado)
        )
        normalizacoes.append({"de": nome, "para": normalizado, "atualizados": r.rowcount})
    if normalizacoes:
        session.commit()

    # ── 2. Cadastra em gestores_cadastrados os nomes restantes que têm
    #       cliente ativo + cup_clientes.status='ativo' ────────────────────
    rows = session.execute(
        text("""
            SELECT DISTINCT c.gestor
            FROM clientes c
            JOIN staging.cup_clientes cc ON cc.task_id = c.cup_task_id
            WHERE c.gestor IS NOT NULL
              AND c.ativo = true
              AND LOWER(COALESCE(cc.status, '')) = 'ativo'
            ORDER BY c.gestor
        """)
    ).all()
    nomes_ativos = [r[0] for r in rows]

    ja_cadastrados = set(
        session.execute(select(GestorCadastrado.nome)).scalars().all()
    )

    cadastrados_agora: list[str] = []
    for nome in nomes_ativos:
        if nome in ja_cadastrados:
            continue
        session.add(GestorCadastrado(nome=nome))
        cadastrados_agora.append(nome)
    if cadastrados_agora:
        session.commit()

    return {
        "normalizacoes": normalizacoes,
        "cadastrados": cadastrados_agora,
        "ja_cadastrados": sorted(ja_cadastrados & set(nomes_ativos)),
        "total_no_dropdown": len(set(nomes_ativos) | ja_cadastrados),
    }


# ── DELETE /gestor/gestores-cadastrados/{id} ──────────────────────────────────

@router.delete("/gestores-cadastrados/{gestor_id}", status_code=204)
def delete_gestor_cadastrado(
    gestor_id: uuid.UUID,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> None:
    g = session.get(GestorCadastrado, gestor_id)
    if not g:
        raise HTTPException(status_code=404, detail="Gestor não encontrado")
    session.delete(g)
    session.commit()


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

    if body.semana_inicio is not None:
        try:
            date.fromisoformat(body.semana_inicio)
        except ValueError:
            raise HTTPException(status_code=400, detail="semana_inicio deve ser YYYY-MM-DD")

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

    # Limpa stale jobs (RUNNING e PENDING) antes de checar duplicatas
    _mark_stale_jobs(session)

    # Impede job duplicado para o mesmo cliente (RUNNING ou PENDING)
    in_progress = session.execute(
        select(ReportJob).where(
            ReportJob.cliente_id == cliente.id,
            ReportJob.status.in_([JobStatus.RUNNING, JobStatus.PENDING]),
        )
    ).scalar_one_or_none()
    if in_progress is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Já existe um job em andamento para este cliente (job_id={in_progress.id}, status={in_progress.status.value})",
        )

    job = ReportJob(
        usuario_id=user.id,
        cliente_id=cliente.id,
        mes=body.mes,
        frequencia=body.frequencia,
        semana_inicio=body.semana_inicio,
        status=JobStatus.PENDING,
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    job_id = job.id
    cliente_slug = cliente.slug
    cliente_nome = cliente.nome
    mes = body.mes
    frequencia = body.frequencia
    semana_inicio = body.semana_inicio

    def _run():
        # Imports DENTRO do try para que qualquer ImportError também caia no handler.
        # Logging em cada transição para diagnosticar travas via Render logs.
        try:
            from db import SessionLocal
            from services.report_slides import gerar_slides

            _log.info("[job %s/%s] thread iniciada", job_id, cliente_nome)

            # Acquire com timeout: se a fila estiver congestionada (threads antigos
            # presos em gerar_slides), falha rápido em vez de bloquear para sempre.
            acquired = _JOB_SEMAPHORE.acquire(timeout=90)
            if not acquired:
                raise TimeoutError(
                    f"Sem vaga na fila após 90s (max concorrente: {_MAX_CONCURRENT_JOBS}). "
                    "Provável trava em jobs anteriores — reinicie o serviço no Render."
                )
            try:
                _log.info("[job %s/%s] semáforo OK, marcando RUNNING", job_id, cliente_nome)

                with SessionLocal() as bg_session:
                    bg_job = bg_session.get(ReportJob, job_id)
                    if bg_job is None:
                        return
                    bg_job.status = JobStatus.RUNNING
                    bg_session.commit()

                _log.info("[job %s/%s] chamando gerar_slides", job_id, cliente_nome)
                url = gerar_slides(slug=cliente_slug, nome_cliente=cliente_nome, mes=mes, frequencia=frequencia, semana_inicio=semana_inicio)
                _log.info("[job %s/%s] gerar_slides retornou url=%s", job_id, cliente_nome, url)

                with SessionLocal() as bg_session:
                    bg_job = bg_session.get(ReportJob, job_id)
                    if bg_job:
                        bg_job.status = JobStatus.DONE
                        bg_job.slides_url = url
                        bg_job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                        bg_session.commit()
                _log.info("[job %s/%s] DONE", job_id, cliente_nome)
            finally:
                _JOB_SEMAPHORE.release()
                # Libera memória de pandas/google clients carregados pelo job
                import gc
                gc.collect()

        except Exception as exc:
            _log.exception("[job %s/%s] FALHOU", job_id, cliente_nome)
            try:
                from db import SessionLocal as _SL
                with _SL() as bg_session:
                    bg_job = bg_session.get(ReportJob, job_id)
                    if bg_job and bg_job.status != JobStatus.DONE:
                        bg_job.status = JobStatus.ERROR
                        bg_job.erro = str(exc)[:500]
                        bg_job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                        bg_session.commit()
            except Exception:
                _log.exception("[job %s] falhou também ao gravar ERROR — ficará preso no DB", job_id)

    threading.Thread(target=_run, daemon=False).start()
    return TriggerResponse(job_id=job.id)


# ── POST /gestor/reports/cleanup-stuck ─────────────────────────────────────
# Endpoint para forçar limpeza de jobs presos em PENDING/RUNNING sem precisar
# reiniciar o serviço no Render. Útil quando threads ficaram travados em
# chamadas Google API que não retornam.

@router.post("/reports/cleanup-stuck", status_code=200)
def cleanup_stuck_jobs(
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    stuck = session.execute(
        select(ReportJob).where(
            ReportJob.status.in_([JobStatus.RUNNING, JobStatus.PENDING]),
        )
    ).scalars().all()
    for job in stuck:
        job.status = JobStatus.ERROR
        job.erro = f"Limpeza manual: job estava em {job.status.value}"
        job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if stuck:
        session.commit()
    return {"cleaned": len(stuck)}


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


# ── GET /gestor/metricas/meses-disponiveis ─────────────────────────────────
# Lista os meses (YYYY-MM) que têm pelo menos um snapshot MENSAL, restritos
# aos clientes do usuário. Usado pelo frontend pra popular o dropdown de
# filtro só com meses que efetivamente têm dados.

@router.get("/metricas/meses-disponiveis", status_code=200)
def metricas_meses_disponiveis(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    from models.snapshot import Snapshot

    if user.is_admin:
        cliente_ids = session.execute(
            select(Cliente.id).where(Cliente.ativo == True)
        ).scalars().all()
    else:
        cliente_ids = session.execute(
            select(Cliente.id)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(UsuarioCliente.usuario_id == user.id, Cliente.ativo == True)
        ).scalars().all()

    if not cliente_ids:
        return {"meses": []}

    rows = session.execute(
        text("""
            SELECT DISTINCT TO_CHAR(periodo_fim, 'YYYY-MM') AS mes
            FROM snapshots
            WHERE frequencia = 'MENSAL'
              AND cliente_id = ANY(:ids)
            ORDER BY mes DESC
        """),
        {"ids": list(cliente_ids)},
    ).all()

    return {"meses": [r[0] for r in rows]}


# ── GET /gestor/metricas ───────────────────────────────────────────────────

@router.get("/metricas", response_model=MetricasDashboardResponse)
def get_metricas_dashboard(
    mes: str | None = Query(None, pattern=r"^\d{4}-\d{2}$", description="Filtro YYYY-MM"),
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> MetricasDashboardResponse:
    from datetime import date, timedelta
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

    # Snapshot MENSAL mais recente por cliente:
    # - se `mes` for passado, restringe periodo_fim ao mês escolhido
    # - se `mes` for None, pega o snapshot mais recente disponível (comportamento legado)
    snapshot_filter = [
        Snapshot.cliente_id.in_(cliente_ids),
        Snapshot.frequencia == "MENSAL",
    ]
    if mes:
        ano, mes_num = int(mes[:4]), int(mes[5:7])
        primeiro = date(ano, mes_num, 1)
        if mes_num == 12:
            ultimo = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            ultimo = date(ano, mes_num + 1, 1) - timedelta(days=1)
        snapshot_filter.append(Snapshot.periodo_fim >= primeiro)
        snapshot_filter.append(Snapshot.periodo_fim <= ultimo)

    sub = (
        select(
            Snapshot.cliente_id,
            func.max(Snapshot.periodo_fim).label("max_fim"),
        )
        .where(*snapshot_filter)
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


# ── GET /gestor/metricas/{slug}/timeline ──────────────────────────────────
# Retorna lista de snapshots MENSAL do cliente nos últimos N meses (default 12),
# ordenados do mais antigo pro mais recente. Usado pra gráfico de evolução
# e KPIs com variação na página de detalhe do cliente.

@router.get("/metricas/{slug}/timeline", status_code=200)
def get_metricas_timeline(
    slug: str,
    meses: int = Query(12, ge=1, le=36),
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    from models.snapshot import Snapshot

    cliente = session.execute(
        select(Cliente).where(Cliente.slug == slug, Cliente.ativo == True)
    ).scalar_one_or_none()
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado")

    if not user.is_admin:
        acesso = session.execute(
            select(UsuarioCliente).where(
                UsuarioCliente.usuario_id == user.id,
                UsuarioCliente.cliente_id == cliente.id,
            )
        ).scalar_one_or_none()
        if not acesso:
            raise HTTPException(403, "Acesso negado")

    from services.metricas import build_timeline
    items = build_timeline(cliente.id, meses, session)

    return {
        "cliente": {
            "slug": cliente.slug,
            "nome": cliente.nome,
            "categoria": cliente.categoria.value,
            "gestor": cliente.gestor,
        },
        "items": items,
    }


@router.get("/metricas/{slug}/breakdown")
def get_metricas_breakdown(
    slug: str,
    mes: str | None = Query(None, pattern=r"^\d{4}-\d{2}$", description="Filtro YYYY-MM"),
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> dict:
    cliente = session.execute(
        select(Cliente).where(Cliente.slug == slug, Cliente.ativo == True)
    ).scalar_one_or_none()
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado")

    if not user.is_admin:
        acesso = session.execute(
            select(UsuarioCliente).where(
                UsuarioCliente.usuario_id == user.id,
                UsuarioCliente.cliente_id == cliente.id,
            )
        ).scalar_one_or_none()
        if not acesso:
            raise HTTPException(403, "Acesso negado")

    from services.metricas import build_breakdown
    return build_breakdown(cliente.id, mes, session)


# ── Geração de insights (lógica compartilhada) ────────────────────────────

def _gerar_insights_para_mes(mes: str, session: Session, settings) -> dict:
    from datetime import date, timedelta, datetime, timezone
    import anthropic as _anthropic
    from models.snapshot import Snapshot
    from services.inteligencia import rodar_detectores
    from services.metricas import build_breakdown as _bd

    ano, mes_num = int(mes[:4]), int(mes[5:7])
    primeiro_atual = date(ano, mes_num, 1)
    ultimo_atual = (date(ano, mes_num + 1, 1) if mes_num < 12 else date(ano + 1, 1, 1)) - timedelta(days=1)

    if mes_num == 1:
        primeiro_ant = date(ano - 1, 12, 1)
        ultimo_ant = date(ano, 1, 1) - timedelta(days=1)
    else:
        primeiro_ant = date(ano, mes_num - 1, 1)
        ultimo_ant = date(ano, mes_num, 1) - timedelta(days=1)

    clientes = session.execute(select(Cliente).where(Cliente.ativo == True)).scalars().all()

    snaps_atual = {
        s.cliente_id: s
        for s in session.execute(
            select(Snapshot).where(
                Snapshot.frequencia == "MENSAL",
                Snapshot.periodo_fim >= primeiro_atual,
                Snapshot.periodo_fim <= ultimo_atual,
            )
        ).scalars().all()
    }

    snaps_ant = {
        s.cliente_id: s
        for s in session.execute(
            select(Snapshot).where(
                Snapshot.frequencia == "MENSAL",
                Snapshot.periodo_fim >= primeiro_ant,
                Snapshot.periodo_fim <= ultimo_ant,
            )
        ).scalars().all()
    }

    investimentos = [float(s.investimento) for s in snaps_atual.values() if s.investimento is not None]
    media_inv = sum(investimentos) / len(investimentos) if investimentos else None

    gerados = sem_sinais = sem_dados = erros = 0

    for cliente in clientes:
        try:
            snap_atual = snaps_atual.get(cliente.id)
            snap_ant = snaps_ant.get(cliente.id)

            if snap_atual is None:
                sem_dados += 1
                continue

            breakdown = _bd(cliente.id, mes, session)
            sinais = rodar_detectores(snap_atual, snap_ant, breakdown, media_inv)

            if not sinais:
                sem_sinais += 1
                continue

            narrativa = None
            if settings.anthropic_api_key:
                try:
                    ant_client = _anthropic.Anthropic(api_key=settings.anthropic_api_key)
                    roas_str = f"{float(snap_atual.roas):.2f}×" if snap_atual.roas else "—"
                    fat_str = f"R${float(snap_atual.faturamento):,.0f}" if snap_atual.faturamento else "—"
                    inv_str = f"R${float(snap_atual.investimento):,.0f}" if snap_atual.investimento else "—"
                    sinais_txt = "\n".join(f"- {s['titulo']}: {s['metrica_principal']}" for s in sinais)
                    prompt = (
                        f"Você é um analista de performance de mídia paga. "
                        f"Analise os sinais abaixo para o cliente {cliente.nome} ({cliente.categoria.value}) "
                        f"no mês de {mes} e escreva um parágrafo objetivo de 3 a 4 frases explicando "
                        f"o que está acontecendo e o que o gestor deve observar. Seja direto, sem jargão excessivo.\n\n"
                        f"Sinais detectados:\n{sinais_txt}\n\n"
                        f"Métricas do mês:\n"
                        f"- Faturamento: {fat_str}\n"
                        f"- Investimento: {inv_str}\n"
                        f"- ROAS geral: {roas_str}"
                    )
                    msg = ant_client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=300,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    narrativa = msg.content[0].text
                except Exception as e:
                    _log.warning("Claude API falhou para %s: %s", cliente.nome, e)

            existing = session.execute(
                select(Insight).where(Insight.cliente_id == cliente.id, Insight.mes == mes)
            ).scalar_one_or_none()

            if existing:
                existing.sinais = sinais
                existing.narrativa = narrativa
                existing.gerado_em = datetime.now(timezone.utc)
            else:
                session.add(Insight(cliente_id=cliente.id, mes=mes, sinais=sinais, narrativa=narrativa))

            session.commit()
            gerados += 1

        except Exception as e:
            _log.error("Erro ao gerar insight para cliente %s: %s", cliente.id, e)
            session.rollback()
            erros += 1

    return {"gerados": gerados, "sem_sinais": sem_sinais, "sem_dados": sem_dados, "erros": erros}


# ── POST /gestor/inteligencia/generate ────────────────────────────────────

@router.post("/inteligencia/generate", status_code=200)
def generate_inteligencia(
    mes: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
    settings=Depends(get_settings),
) -> InteligenciaGenerateResponse:
    counts = _gerar_insights_para_mes(mes, session, settings)
    return InteligenciaGenerateResponse(mes=mes, **counts)


# ── GET /gestor/inteligencia ───────────────────────────────────────────────

_SEV_ORDER = {"critico": 0, "atencao": 1, "oportunidade": 2}


@router.get("/inteligencia", status_code=200)
def get_inteligencia(
    mes: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    gestor: str | None = Query(None),
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
    settings=Depends(get_settings),
) -> InteligenciaResponse:
    # Geração lazy: se não há nenhum insight para o mês, gera agora
    existe = session.execute(
        select(Insight.id).where(Insight.mes == mes).limit(1)
    ).scalar_one_or_none()
    if existe is None:
        _gerar_insights_para_mes(mes, session, settings)

    cliente_query = select(Cliente).where(Cliente.ativo == True)

    if user.is_admin:
        if gestor:
            cliente_query = cliente_query.where(Cliente.gestor == gestor)
    else:
        cliente_query = cliente_query.join(
            UsuarioCliente,
            (UsuarioCliente.cliente_id == Cliente.id)
            & (UsuarioCliente.usuario_id == user.id),
        )

    clientes = session.execute(cliente_query).scalars().all()
    cliente_ids = [c.id for c in clientes]
    cliente_map = {c.id: c for c in clientes}

    if not cliente_ids:
        return InteligenciaResponse(mes=mes, alertas=[])

    insights = session.execute(
        select(Insight).where(
            Insight.cliente_id.in_(cliente_ids),
            Insight.mes == mes,
        )
    ).scalars().all()

    alertas = [
        InteligenciaAlerta(
            cliente_slug=cliente_map[i.cliente_id].slug,
            cliente_nome=cliente_map[i.cliente_id].nome,
            cliente_categoria=cliente_map[i.cliente_id].categoria.value,
            severidade=min(i.sinais, key=lambda s: _SEV_ORDER.get(s["severidade"], 99))["severidade"] if i.sinais else "atencao",
            sinais=i.sinais,
            narrativa=i.narrativa,
        )
        for i in insights
        if i.cliente_id in cliente_map
    ]

    alertas.sort(key=lambda a: _SEV_ORDER.get(a.severidade, 99))

    return InteligenciaResponse(mes=mes, alertas=alertas)


# ── Base histórica / Backfill ETL ────────────────────────────────────────────

@router.post("/admin/etl/backfill", status_code=202, response_model=BackfillResponse)
def trigger_backfill(
    body: BackfillRequest,
    user: Usuario = Depends(require_admin),
):
    """Dispara backfill ETL para um intervalo de meses em background."""
    if not _MES_RE.match(body.mes_inicio) or not _MES_RE.match(body.mes_fim):
        raise HTTPException(400, "mes_inicio e mes_fim devem estar no formato YYYY-MM")
    if body.mes_inicio > body.mes_fim:
        raise HTTPException(400, "mes_inicio deve ser <= mes_fim")

    ano_i, mes_i = int(body.mes_inicio[:4]), int(body.mes_inicio[5:])
    ano_f, mes_f = int(body.mes_fim[:4]), int(body.mes_fim[5:])
    meses_total = (ano_f - ano_i) * 12 + (mes_f - mes_i) + 1
    if meses_total > 36:
        raise HTTPException(400, "Intervalo máximo de 36 meses")

    if any(j["status"] == "running" for j in _backfill_jobs.values()):
        raise HTTPException(409, "Já existe um backfill em andamento. Aguarde a conclusão antes de iniciar outro.")

    with SessionLocal() as session:
        if body.slug:
            cliente_exists = session.execute(
                select(Cliente.id).where(Cliente.slug == body.slug)
            ).scalar_one_or_none()
            if cliente_exists is None:
                raise HTTPException(404, f"Cliente com slug '{body.slug}' não encontrado")
            n_clientes = 1
        else:
            n_clientes = session.execute(
                select(func.count(Cliente.id)).where(Cliente.ativo == True)
            ).scalar_one()

    job_id = str(uuid.uuid4())
    _backfill_jobs[job_id] = {
        "status": "running",
        "meses_total": meses_total,
        "meses_concluidos": 0,
        "erros": 0,
        "pct": 0,
    }

    def _run() -> None:
        def _progress(concluidos: int, total: int, erros: int) -> None:
            _backfill_jobs[job_id]["meses_concluidos"] = concluidos
            _backfill_jobs[job_id]["erros"] = erros
            _backfill_jobs[job_id]["pct"] = int(concluidos / total * 100) if total else 0

        try:
            from etl.collect import backfill_clientes_meses
            backfill_clientes_meses(
                mes_inicio=body.mes_inicio,
                mes_fim=body.mes_fim,
                slug=body.slug,
                progress_callback=_progress,
            )
            _backfill_jobs[job_id]["status"] = "done"
            _backfill_jobs[job_id]["pct"] = 100
        except Exception:
            _log.exception("[backfill %s] FALHOU", job_id)
            _backfill_jobs[job_id]["status"] = "error"

    threading.Thread(target=_run, daemon=False).start()

    return BackfillResponse(job_id=job_id, meses=meses_total, clientes=n_clientes)


@router.get("/admin/etl/backfill/{job_id}", response_model=BackfillJobStatusResponse)
def get_backfill_status(
    job_id: str,
    user: Usuario = Depends(require_admin),
):
    """Retorna o status de um job de backfill em andamento."""
    job = _backfill_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return BackfillJobStatusResponse(job_id=job_id, **job)


@router.get("/admin/cobertura", response_model=CoberturaResponse)
def get_cobertura(
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
):
    """Retorna matriz de cobertura: para cada cliente, quais meses têm snapshot."""
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    meses: list[str] = []
    for _ in range(36):
        meses.insert(0, f"{ano:04d}-{mes:02d}")
        mes -= 1
        if mes == 0:
            mes = 12
            ano -= 1

    clientes = session.execute(
        select(Cliente).order_by(Cliente.nome)
    ).scalars().all()

    cutoff_str = meses[0]  # "YYYY-MM"
    cutoff_ano, cutoff_mes = int(cutoff_str[:4]), int(cutoff_str[5:])
    cutoff_date = date(cutoff_ano, cutoff_mes, 1)

    snaps = session.execute(
        select(Snapshot.cliente_id, Snapshot.periodo_inicio)
        .where(Snapshot.frequencia == SnapFrequencia.MENSAL)
        .where(Snapshot.periodo_inicio >= cutoff_date)
    ).all()

    meses_por_cliente: dict[uuid.UUID, set[str]] = defaultdict(set)
    for s in snaps:
        meses_por_cliente[s.cliente_id].add(s.periodo_inicio.strftime("%Y-%m"))

    return CoberturaResponse(
        meses=meses,
        clientes=[
            CoberturaClienteItem(
                id=c.id,
                slug=c.slug,
                nome=c.nome,
                ativo=c.ativo,
                meses_com_snapshot=sorted(meses_por_cliente.get(c.id, set())),
            )
            for c in clientes
        ],
    )


# ── GET /gestor/criativos ──────────────────────────────────────────────────

@router.get("/criativos", response_model=CriativosResponse)
def list_criativos(
    de: date = Query(..., description="YYYY-MM-DD inclusive"),
    ate: date = Query(..., description="YYYY-MM-DD inclusive"),
    rede: Literal["meta", "google", "todos"] = Query("todos"),
    categoria: list[Literal["ECOMMERCE", "LEAD_COM_SITE", "LEAD_SEM_SITE"]] | None = Query(None),
    gestor: str | None = Query(None),
    cliente: str | None = Query(None, description="slug do cliente"),
    fat_min: float | None = Query(None),
    fat_max: float | None = Query(None),
    inv_min: float | None = Query(None),
    inv_max: float | None = Query(None),
    cli_fat_min: float | None = Query(None),
    cli_fat_max: float | None = Query(None),
    cli_inv_min: float | None = Query(None),
    cli_inv_max: float | None = Query(None),
    order_by: Literal["roas", "faturamento", "investimento"] = Query("roas"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> CriativosResponse:
    items, total, totais = agregar_criativos(
        session,
        de=de,
        ate=ate,
        rede=rede,
        categorias=list(categoria) if categoria else None,
        gestor=gestor,
        cliente_slug=cliente,
        fat_min=fat_min,
        fat_max=fat_max,
        inv_min=inv_min,
        inv_max=inv_max,
        cli_fat_min=cli_fat_min,
        cli_fat_max=cli_fat_max,
        cli_inv_min=cli_inv_min,
        cli_inv_max=cli_inv_max,
        order_by=order_by,
        limit=limit,
        offset=offset,
        user=user,
    )
    for it in items:
        if it.thumb_status == "ok":
            it.thumb_url = f"/api/gestor/criativos/{it.criativo_id}/thumb"
        else:
            it.thumb_url = None
    return CriativosResponse(items=items, total=total, totais=totais)


# ── GET /gestor/criativos/{criativo_id}/thumb ──────────────────────────────

@router.get("/criativos/{criativo_id}/thumb")
def get_criativo_thumb(
    criativo_id: uuid.UUID,
    request: Request,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> Response:
    criativo = session.get(Criativo, criativo_id)
    if criativo is None or criativo.thumb_status != ThumbStatus.OK:
        raise HTTPException(status_code=404, detail="Thumb não encontrada")

    # Escopo de acesso: admin tudo; gestor valida UsuarioCliente.
    if not user.is_admin:
        autorizado = session.execute(
            select(UsuarioCliente.cliente_id).where(
                UsuarioCliente.usuario_id == user.id,
                UsuarioCliente.cliente_id == criativo.cliente_id,
            )
        ).scalar_one_or_none()
        if autorizado is None:
            raise HTTPException(status_code=404, detail="Thumb não encontrada")

    etag = f'"{criativo_id}"'
    cache_headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)

    thumb = session.get(CriativoThumb, criativo_id)
    if thumb is None:
        raise HTTPException(status_code=404, detail="Thumb não encontrada")

    return Response(
        content=thumb.conteudo,
        media_type=thumb.mime,
        headers=cache_headers,
    )

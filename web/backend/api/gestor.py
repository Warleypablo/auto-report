from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import distinct, select, text, update
from sqlalchemy.orm import Session, selectinload

from api.auth import require_admin, require_auth
from db import get_session
from models import Cliente, GestorCadastrado, ReportJob, Usuario, UsuarioCliente
from models.cliente import Categoria as CatEnum
from models.report_job import JobStatus
from etl.cliente_publico import slugify
from schemas import (
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
# Tenta vincular clientes sem cup_task_id usando matching tolerante:
# - normaliza nome (lower, sem acentos, sem sufixos jurídicos, sem pontuação)
# - só aplica match se houver candidato ÚNICO (sem ambiguidade)
# - dry_run=true (default) retorna proposta sem aplicar

import re
import unicodedata
from collections import defaultdict


_SUFIXOS_JURIDICOS_RE = re.compile(
    r"\s+(ltda|me|mei|epp|eireli|s\.?a\.?|sa|inc\.?|corp\.?)\s*\.?\s*$",
    re.IGNORECASE,
)


def _normalize_nome(s: str | None) -> str:
    if not s:
        return ""
    # Remove acentos
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    # Remove sufixos jurídicos no fim
    s = _SUFIXOS_JURIDICOS_RE.sub("", s)
    # Remove pontuação (mantém alfanumérico + espaço)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    # Colapsa espaços
    s = re.sub(r"\s+", " ", s).strip()
    return s


@router.post("/clickup/automatch", status_code=200)
def automatch_clickup(
    dry_run: bool = Query(True),
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    # 1. Carrega todas as tasks do ClickUp e agrupa por nome normalizado
    cup_rows = session.execute(
        text("SELECT task_id, nome FROM staging.cup_clientes WHERE nome IS NOT NULL AND TRIM(nome) <> ''")
    ).mappings().all()

    cup_by_norm: dict[str, list[dict]] = defaultdict(list)
    for r in cup_rows:
        norm = _normalize_nome(r["nome"])
        if norm:
            cup_by_norm[norm].append({"task_id": r["task_id"], "nome": r["nome"]})

    # 2. Carrega clientes ativos sem vínculo
    clientes = session.execute(
        select(Cliente)
        .where(Cliente.cup_task_id.is_(None), Cliente.ativo == True)
        .order_by(Cliente.nome.asc())
    ).scalars().all()

    # 3. Pra cada cliente, tenta match
    matches: list[dict] = []
    ambiguos: list[dict] = []
    sem_candidato: list[dict] = []

    for c in clientes:
        norm = _normalize_nome(c.nome)
        candidates = cup_by_norm.get(norm, [])

        if len(candidates) == 1:
            matches.append({
                "cliente_id": str(c.id),
                "cliente_nome": c.nome,
                "task_id": candidates[0]["task_id"],
                "cup_nome": candidates[0]["nome"],
            })
        elif len(candidates) > 1:
            ambiguos.append({
                "cliente_id": str(c.id),
                "cliente_nome": c.nome,
                "candidatos": candidates,
            })
        else:
            sem_candidato.append({
                "cliente_id": str(c.id),
                "cliente_nome": c.nome,
            })

    # 4. Aplica se não for dry_run
    aplicados = 0
    if not dry_run and matches:
        for m in matches:
            # Re-verifica que ninguém pegou esse task_id no meio do caminho
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
    """Atribui clientes.gestor = responsável do contrato 'Performance' no ClickUp.

    Caminho do dado (relaciona por NOME, não por cup_task_id):
      clientes.nome  ←normaliza→  staging.cup_clientes.nome
                                   ↓
                                   subtask_ids  (string com ";" como separador)
                                   ↓ split
                                   ↓ JOIN com cup_contratos.id_subtask
                                   ↓ filtra servico ILIKE '%performance%'
                                   ↓ contrato mais recente por data_inicio
                                   responsavel  →  clientes.gestor
    """
    # Subquery de normalização compartilhada entre clientes e cup_clientes.
    # Usa TRANSLATE para remover acentos comuns + LOWER + colapso de espaços.
    sql_norm = """
        LOWER(REGEXP_REPLACE(TRANSLATE(TRIM($1),
            'ÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÇÑáàâãäåèéêëìíîïòóôõöùúûüçñ',
            'AAAAAAEEEEIIIIOOOOOUUUUCNaaaaaaeeeeiiiiooooouuuucn'),
            '\\s+', ' ', 'g'))
    """  # noqa — placeholder, será inlineado abaixo

    # Pré-contagem com a mesma lógica do UPDATE pra mostrar pro admin onde estão as lacunas
    counts = session.execute(
        text("""
            WITH cliente_norm AS (
                SELECT
                    c.id,
                    c.nome,
                    c.gestor,
                    LOWER(REGEXP_REPLACE(TRANSLATE(TRIM(c.nome),
                        'ÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÇÑáàâãäåèéêëìíîïòóôõöùúûüçñ',
                        'AAAAAAEEEEIIIIOOOOOUUUUCNaaaaaaeeeeiiiiooooouuuucn'),
                        '\\s+', ' ', 'g')) AS nome_norm
                FROM clientes c
                WHERE c.ativo = true
            ),
            cup_norm AS (
                SELECT
                    cc.nome,
                    cc.subtask_ids,
                    LOWER(REGEXP_REPLACE(TRANSLATE(TRIM(cc.nome),
                        'ÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÇÑáàâãäåèéêëìíîïòóôõöùúûüçñ',
                        'AAAAAAEEEEIIIIOOOOOUUUUCNaaaaaaeeeeiiiiooooouuuucn'),
                        '\\s+', ' ', 'g')) AS nome_norm
                FROM staging.cup_clientes cc
            ),
            cliente_matched AS (
                SELECT cn.id, cn.gestor, cup.subtask_ids
                FROM cliente_norm cn
                JOIN cup_norm cup ON cn.nome_norm = cup.nome_norm
            ),
            subtasks_explodidas AS (
                SELECT cm.id AS cliente_id, cm.gestor, TRIM(s.subtask_id) AS subtask_id
                FROM cliente_matched cm
                CROSS JOIN LATERAL UNNEST(STRING_TO_ARRAY(cm.subtask_ids, ';')) AS s(subtask_id)
                WHERE COALESCE(cm.subtask_ids, '') <> ''
            ),
            performance_resp AS (
                SELECT DISTINCT ON (se.cliente_id)
                    se.cliente_id,
                    se.gestor AS gestor_atual,
                    ct.responsavel AS novo_gestor
                FROM subtasks_explodidas se
                JOIN staging.cup_contratos ct ON TRIM(ct.id_subtask) = se.subtask_id
                WHERE LOWER(ct.servico) LIKE '%performance%'
                ORDER BY se.cliente_id, ct.data_inicio DESC NULLS LAST
            )
            SELECT
                (SELECT COUNT(*) FROM clientes WHERE ativo = true) AS total_ativos,
                (SELECT COUNT(*) FROM cliente_matched) AS com_match_nome,
                (SELECT COUNT(*) FROM performance_resp) AS com_contrato_performance,
                (SELECT COUNT(*) FROM performance_resp WHERE novo_gestor IS NOT NULL AND TRIM(novo_gestor) <> '') AS com_responsavel,
                (SELECT COUNT(*) FROM performance_resp pr
                  WHERE pr.novo_gestor IS NOT NULL AND TRIM(pr.novo_gestor) <> ''
                    AND pr.gestor_atual IS DISTINCT FROM pr.novo_gestor) AS a_atualizar
        """)
    ).mappings().one()

    # UPDATE: aplica o gestor onde tudo bate
    result = session.execute(
        text("""
            WITH cliente_norm AS (
                SELECT
                    c.id, c.gestor,
                    LOWER(REGEXP_REPLACE(TRANSLATE(TRIM(c.nome),
                        'ÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÇÑáàâãäåèéêëìíîïòóôõöùúûüçñ',
                        'AAAAAAEEEEIIIIOOOOOUUUUCNaaaaaaeeeeiiiiooooouuuucn'),
                        '\\s+', ' ', 'g')) AS nome_norm
                FROM clientes c
                WHERE c.ativo = true
            ),
            cup_norm AS (
                SELECT
                    cc.subtask_ids,
                    LOWER(REGEXP_REPLACE(TRANSLATE(TRIM(cc.nome),
                        'ÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÇÑáàâãäåèéêëìíîïòóôõöùúûüçñ',
                        'AAAAAAEEEEIIIIOOOOOUUUUCNaaaaaaeeeeiiiiooooouuuucn'),
                        '\\s+', ' ', 'g')) AS nome_norm
                FROM staging.cup_clientes cc
                WHERE COALESCE(cc.subtask_ids, '') <> ''
            ),
            cliente_matched AS (
                SELECT cn.id, cn.gestor, cup.subtask_ids
                FROM cliente_norm cn
                JOIN cup_norm cup ON cn.nome_norm = cup.nome_norm
            ),
            subtasks_explodidas AS (
                SELECT cm.id AS cliente_id, TRIM(s.subtask_id) AS subtask_id
                FROM cliente_matched cm
                CROSS JOIN LATERAL UNNEST(STRING_TO_ARRAY(cm.subtask_ids, ';')) AS s(subtask_id)
            ),
            performance_resp AS (
                SELECT DISTINCT ON (se.cliente_id)
                    se.cliente_id,
                    ct.responsavel AS novo_gestor
                FROM subtasks_explodidas se
                JOIN staging.cup_contratos ct ON TRIM(ct.id_subtask) = se.subtask_id
                WHERE LOWER(ct.servico) LIKE '%performance%'
                  AND ct.responsavel IS NOT NULL
                  AND TRIM(ct.responsavel) <> ''
                ORDER BY se.cliente_id, ct.data_inicio DESC NULLS LAST
            )
            UPDATE clientes c
            SET gestor = pr.novo_gestor,
                atualizado_em = NOW()
            FROM performance_resp pr
            WHERE c.id = pr.cliente_id
              AND (c.gestor IS DISTINCT FROM pr.novo_gestor)
        """)
    )
    session.commit()

    _log.info(
        "sync-gestores: atualizados=%d | total_ativos=%d com_match_nome=%d com_contrato_performance=%d com_responsavel=%d",
        result.rowcount, counts["total_ativos"], counts["com_match_nome"],
        counts["com_contrato_performance"], counts["com_responsavel"],
    )

    return {
        "atualizados": result.rowcount,
        "total_ativos": counts["total_ativos"],
        "com_match_nome": counts["com_match_nome"],
        "com_contrato_performance": counts["com_contrato_performance"],
        "com_responsavel": counts["com_responsavel"],
    }


# ── GET /gestor/clientes ───────────────────────────────────────────────────

@router.get("/clientes", response_model=ClientesGestorResponse)
def list_clientes(
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
) -> ClientesGestorResponse:
    from sqlalchemy import text

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
                WHERE c.ativo = true
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
    """Lista gestores distintos com pelo menos 1 cliente ATIVO no ClickUp.

    Filtro reduz lista de ~30 (todos os gestores históricos) para os que
    têm conta ativa hoje. Requer cup_task_id populado em clientes.
    """
    # SQL bruto: precisa do JOIN com staging.cup_clientes que SQLAlchemy
    # não mapeia (tabela externa, sem model). Mantém o filtro de acesso
    # (admin vê tudo; não-admin só seus clientes vinculados).
    base_sql = """
        SELECT DISTINCT c.gestor
        FROM clientes c
        JOIN staging.cup_clientes cc ON cc.task_id = c.cup_task_id
    """
    where = """
        WHERE c.gestor IS NOT NULL
          AND c.ativo = true
          AND LOWER(COALESCE(cc.status, '')) = 'ativo'
    """
    if user.is_admin:
        sql = base_sql + where + " ORDER BY c.gestor"
        params: dict = {}
    else:
        sql = (
            base_sql
            + " JOIN usuario_clientes uc ON uc.cliente_id = c.id"
            + where
            + " AND uc.usuario_id = :uid ORDER BY c.gestor"
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
                url = gerar_slides(slug=cliente_slug, nome_cliente=cliente_nome, mes=mes, frequencia=frequencia)
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

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from db import get_session
from models import Cliente, Snapshot
from schemas import CaseDetail, CaseListItem
from services.case_builder import build_case_detail, build_case_list_item

router = APIRouter()


class CaseListResponse(BaseModel):
    items: list[CaseListItem]
    total: int


def _latest_snapshot_subquery():
    return (
        select(Snapshot.cliente_id, Snapshot.id.label("snap_id"))
        .distinct(Snapshot.cliente_id)
        .order_by(Snapshot.cliente_id, Snapshot.periodo_fim.desc(), Snapshot.data_coleta.desc())
    ).subquery()


@router.get("/cases", response_model=CaseListResponse)
def list_cases(
    categoria: str | None = Query(default=None),
    setor: str | None = Query(default=None),
    order_by: Literal["roas", "faturamento", "crescimento"] = Query(default="faturamento"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> CaseListResponse:
    sub = _latest_snapshot_subquery()

    stmt = (
        select(Cliente, Snapshot)
        .join(sub, sub.c.cliente_id == Cliente.id)
        .join(Snapshot, Snapshot.id == sub.c.snap_id)
        .where(Cliente.publicar_vitrine.is_(True))
    )
    if categoria:
        stmt = stmt.where(Cliente.categoria == categoria)
    if setor:
        stmt = stmt.where(Cliente.setor == setor)

    if order_by == "roas":
        stmt = stmt.order_by(Snapshot.roas.desc().nulls_last())
    elif order_by == "crescimento":
        stmt = stmt.order_by(Snapshot.faturamento_var_pct.desc().nulls_last())
    else:
        stmt = stmt.order_by(Snapshot.faturamento.desc().nulls_last())

    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.scalar(total_stmt) or 0

    rows = session.execute(stmt.limit(limit).offset(offset)).all()
    items = [build_case_list_item(c, s) for (c, s) in rows]
    return CaseListResponse(items=items, total=total)


@router.get("/cases/{slug}", response_model=CaseDetail)
def get_case(slug: str, session: Session = Depends(get_session)) -> CaseDetail:
    cliente = session.scalar(
        select(Cliente)
        .where(Cliente.slug == slug, Cliente.publicar_vitrine.is_(True))
        .options(joinedload(Cliente.snapshots))
    )
    if cliente is None or not cliente.snapshots:
        raise HTTPException(404, "Case não encontrado")

    snapshots = sorted(cliente.snapshots, key=lambda s: s.periodo_fim)
    atual = snapshots[-1]
    historico = snapshots[-12:]
    return build_case_detail(cliente, atual, historico)

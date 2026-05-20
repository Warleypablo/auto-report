from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models import Snapshot
from models.snapshot import Frequencia


def upsert_snapshot(
    session: Session,
    *,
    cliente_id: uuid.UUID,
    periodo_inicio: date,
    periodo_fim: date,
    frequencia: Frequencia,
    dados: dict,
) -> Snapshot:
    payload = {
        "cliente_id": cliente_id,
        "periodo_inicio": periodo_inicio,
        "periodo_fim": periodo_fim,
        "frequencia": frequencia,
        **dados,
    }
    stmt = insert(Snapshot).values(**payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_snapshot_periodo",
        set_={
            k: v for k, v in payload.items()
            if k not in {"cliente_id", "periodo_inicio", "periodo_fim", "frequencia"}
        },
    )
    session.execute(stmt)
    return session.scalar(
        select(Snapshot).where(
            Snapshot.cliente_id == cliente_id,
            Snapshot.periodo_inicio == periodo_inicio,
            Snapshot.periodo_fim == periodo_fim,
        )
    )

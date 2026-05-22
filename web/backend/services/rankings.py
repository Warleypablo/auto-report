from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Cliente, Snapshot

RankingTipo = Literal["roas", "faturamento", "crescimento"]

COLUNA = {
    "roas": Snapshot.roas,
    "faturamento": Snapshot.faturamento,
    "crescimento": Snapshot.faturamento_var_pct,
}

COLUNA_NOME = {
    "roas": "roas",
    "faturamento": "faturamento",
    "crescimento": "faturamento_var_pct",
}


def top_n(session: Session, tipo: RankingTipo, limit: int) -> list[tuple[Cliente, Snapshot]]:
    sub = (
        select(Snapshot.cliente_id, Snapshot.id.label("snap_id"))
        .distinct(Snapshot.cliente_id)
        .order_by(Snapshot.cliente_id, Snapshot.periodo_fim.desc(), Snapshot.data_coleta.desc())
    ).subquery()

    coluna = COLUNA[tipo]
    stmt = (
        select(Cliente, Snapshot)
        .join(sub, sub.c.cliente_id == Cliente.id)
        .join(Snapshot, Snapshot.id == sub.c.snap_id)
        .where(Cliente.publicar_vitrine.is_(True), coluna.is_not(None))
        .order_by(coluna.desc())
        .limit(limit)
    )
    return list(session.execute(stmt).all())

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session


def build_timeline(cliente_id: uuid.UUID, meses: int, session: Session) -> list[dict]:
    """Snapshots MENSAL dos últimos N meses, ordem cronológica (antigo → recente).

    Retorna a estrutura interna que os controllers usam para montar o response
    final (gestor inclui campos extras, cliente filtra os internos).
    """
    from models.snapshot import Snapshot

    snapshots = session.execute(
        select(Snapshot)
        .where(Snapshot.cliente_id == cliente_id, Snapshot.frequencia == "MENSAL")
        .order_by(Snapshot.periodo_fim.desc())
        .limit(meses)
    ).scalars().all()

    snapshots = list(reversed(snapshots))

    return [
        {
            "mes": s.periodo_fim.strftime("%Y-%m"),
            "periodo_inicio": str(s.periodo_inicio),
            "periodo_fim": str(s.periodo_fim),
            "faturamento": float(s.faturamento) if s.faturamento is not None else None,
            "investimento": float(s.investimento) if s.investimento is not None else None,
            "roas": float(s.roas) if s.roas is not None else None,
            "cpa": float(s.cpa) if s.cpa is not None else None,
            "leads": s.leads,
            "vendas": s.vendas,
            "faturamento_var_pct": float(s.faturamento_var_pct) if s.faturamento_var_pct is not None else None,
            "roas_var_pct": float(s.roas_var_pct) if s.roas_var_pct is not None else None,
        }
        for s in snapshots
    ]

from __future__ import annotations

import logging
import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

# Garante que a raiz do repo (auto-report) está no PYTHONPATH para `core`/`config`.
# parents[3] = /Users/.../auto-report-main (mesmo cálculo de etl/collect.py).
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from models import AdInsight, Criativo, CriativoThumb, RedeAnuncio, ThumbStatus

log = logging.getLogger(__name__)

RETROACAO_DIAS = 3


def upsert_ad_insight(
    session: Session,
    *,
    cliente_id: uuid.UUID,
    rede: RedeAnuncio,
    ad_id: str,
    dia: date,
    investimento: Decimal,
    faturamento: Decimal,
    conversoes: Decimal,
    leads: int | None,
    impressoes: int,
    clicks: int,
    video_3s: int | None,
    reach: int | None,
) -> None:
    """Upsert idempotente de uma linha diária de insight (constraint
    uq_ad_insight_cliente_rede_ad_dia). Reescreve as métricas no conflito —
    suporta a janela de retroação que reprocessa dias já gravados."""
    payload = dict(
        cliente_id=cliente_id,
        rede=rede,
        ad_id=ad_id,
        dia=dia,
        investimento=investimento,
        faturamento=faturamento,
        conversoes=conversoes,
        leads=leads,
        impressoes=impressoes,
        clicks=clicks,
        video_3s=video_3s,
        reach=reach,
    )
    stmt = insert(AdInsight).values(**payload)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_ad_insight_cliente_rede_ad_dia",
        set_={
            k: v
            for k, v in payload.items()
            if k not in {"cliente_id", "rede", "ad_id", "dia"}
        },
    )
    session.execute(stmt)


def upsert_criativo(
    session: Session,
    *,
    cliente_id: uuid.UUID,
    rede: RedeAnuncio,
    ad_id: str,
    nome: str | None,
    tipo: str | None,
    preview_link: str | None,
    dia: date,
) -> None:
    """Upsert idempotente da dimensão (constraint uq_criativo_cliente_rede_ad).
    No conflito: atualiza nome/tipo/preview_link, expande primeiro_dia (LEAST)
    e ultimo_dia (GREATEST), e PRESERVA thumb_status (gerenciado pela coleta de
    thumb, não pelo upsert de metadados)."""
    payload = dict(
        cliente_id=cliente_id,
        rede=rede,
        ad_id=ad_id,
        nome=nome,
        tipo=tipo,
        preview_link=preview_link,
        primeiro_dia=dia,
        ultimo_dia=dia,
    )
    stmt = insert(Criativo).values(**payload)
    col = Criativo.__table__.c
    stmt = stmt.on_conflict_do_update(
        constraint="uq_criativo_cliente_rede_ad",
        set_={
            "nome": stmt.excluded.nome,
            "tipo": stmt.excluded.tipo,
            "preview_link": stmt.excluded.preview_link,
            "primeiro_dia": func.least(col.primeiro_dia, stmt.excluded.primeiro_dia),
            "ultimo_dia": func.greatest(col.ultimo_dia, stmt.excluded.ultimo_dia),
        },
    )
    session.execute(stmt)

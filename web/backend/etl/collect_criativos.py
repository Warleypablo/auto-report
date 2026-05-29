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

import json

import httpx

from config.settings import ACCESS_TOKEN_META_SYSTEM
from core.categorias.ecommerce.campaign_facebook_gather import (
    _extract_purchase_metrics,
    _video_3s_views_from_row,
)
from models import AdInsight, Criativo, CriativoThumb, RedeAnuncio, ThumbStatus

log = logging.getLogger(__name__)

META_API_VERSION = "v23.0"
TIMEOUT = 30
_BATCH_SIZE = 50
_ATTR_WINDOW = ["7d_click"]

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


def _meta_insights_diarios(ad_account_id: str, since: date, until: date) -> list[dict]:
    """Chama /act_{id}/insights level=ad time_increment=1 e devolve uma lista de
    dicts normalizados, um por (ad_id, dia). Reusa o parsing de actions/
    action_values/video_3s do core (campaign_facebook_gather)."""
    acct_path = f"act_{ad_account_id.removeprefix('act_')}"
    url = f"https://graph.facebook.com/{META_API_VERSION}/{acct_path}/insights"
    params = {
        "level": "ad",
        "time_increment": 1,
        "time_range": json.dumps(
            {"since": since.strftime("%Y-%m-%d"), "until": until.strftime("%Y-%m-%d")},
            separators=(",", ":"),
        ),
        "fields": (
            "ad_id,ad_name,spend,impressions,clicks,reach,"
            "actions,action_values,video_3_sec_watched_actions"
        ),
        "action_attribution_windows": json.dumps(_ATTR_WINDOW, separators=(",", ":")),
        "action_report_time": "conversion",
        "limit": 5000,
        "access_token": ACCESS_TOKEN_META_SYSTEM,
    }

    linhas: list[dict] = []
    next_url: str | None = url
    next_params: dict | None = params
    while next_url:
        resp = httpx.get(next_url, params=next_params, timeout=TIMEOUT,
                         follow_redirects=True)
        resp.raise_for_status()
        body = resp.json()
        for row in body.get("data", []):
            ad_id = row.get("ad_id")
            if not ad_id:
                continue
            conv, fat = _extract_purchase_metrics(
                row.get("actions") or [], row.get("action_values") or []
            )
            linhas.append({
                "ad_id": ad_id,
                "ad_name": row.get("ad_name"),
                "dia": date.fromisoformat(row["date_start"]),
                "investimento": Decimal(str(row.get("spend") or "0")),
                "faturamento": Decimal(str(fat or 0)),
                "conversoes": Decimal(str(conv or 0)),
                "impressoes": int(row.get("impressions") or 0),
                "clicks": int(row.get("clicks") or 0),
                "reach": int(row["reach"]) if row.get("reach") is not None else None,
                "video_3s": _video_3s_views_from_row(row),
            })
        paging = body.get("paging", {}) or {}
        next_url = paging.get("next")
        next_params = None  # o link "next" já vem com todos os params/cursor
    return linhas


def _meta_metadados_lote(ad_ids: list[str]) -> dict[str, dict]:
    """Busca nome/tipo/preview-link/imagem por ad_id em lotes de _BATCH_SIZE via
    endpoint ?ids=. Retorna {ad_id: {nome, tipo, preview_link, imagem_url}}.
    imagem_url prefere creative.image_url e cai para creative.thumbnail_url."""
    out: dict[str, dict] = {}
    base = f"https://graph.facebook.com/{META_API_VERSION}"
    for i in range(0, len(ad_ids), _BATCH_SIZE):
        chunk = [a for a in ad_ids[i : i + _BATCH_SIZE] if a]
        if not chunk:
            continue
        params = {
            "ids": ",".join(chunk),
            "fields": "name,creative{thumbnail_url,image_url,object_type},preview_shareable_link",
            "access_token": ACCESS_TOKEN_META_SYSTEM,
        }
        resp = httpx.get(base, params=params, timeout=TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        for ad_id, obj in (resp.json() or {}).items():
            creative = obj.get("creative") or {}
            object_type = creative.get("object_type")
            out[ad_id] = {
                "nome": obj.get("name"),
                "tipo": object_type.lower() if object_type else None,
                "preview_link": obj.get("preview_shareable_link"),
                "imagem_url": creative.get("image_url") or creative.get("thumbnail_url"),
            }
    return out

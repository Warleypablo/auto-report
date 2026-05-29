from __future__ import annotations

import argparse
import logging
import sys
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Garante que a raiz do repo (auto-report) está no PYTHONPATH para `core`/`config`.
# parents[3] = /Users/.../auto-report-main (mesmo cálculo de etl/collect.py).
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import func, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

import json

import httpx

from app_settings import get_settings
from config.settings import ACCESS_TOKEN_META_SYSTEM
from core.cred_manager import _build_google_ads_client
from google.ads.googleads.errors import GoogleAdsException
from core.categorias.ecommerce.campaign_facebook_gather import (
    _extract_purchase_metrics,
    _video_3s_views_from_row,
)
from db import SessionLocal, engine
from etl.lock import LockTaken, advisory_lock
from models import AdInsight, Criativo, CriativoThumb, RedeAnuncio, ThumbStatus
from models import Cliente

from .thumbnails import fetch_e_redimensionar

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


def _get_google_ads_service():
    """Wrapper para permitir mock em testes (espelha etl.collect._get_handler)."""
    client = _build_google_ads_client()
    return client.get_service("GoogleAdsService")


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


def _gravar_thumb(session: Session, criativo_id: uuid.UUID, conteudo: bytes, mime: str) -> None:
    """Upsert idempotente de criativo_thumbs (PK criativo_id)."""
    payload = dict(criativo_id=criativo_id, conteudo=conteudo, mime=mime)
    stmt = insert(CriativoThumb).values(**payload)
    stmt = stmt.on_conflict_do_update(
        index_elements=[CriativoThumb.criativo_id],
        set_={"conteudo": stmt.excluded.conteudo, "mime": stmt.excluded.mime},
    )
    session.execute(stmt)


def coletar_criativos_meta(
    cliente: Cliente,
    since: date,
    until: date,
    session_factory: Callable[[], Session] = SessionLocal,
) -> bool:
    """Coleta insights ad-level Meta (time_increment=1) + metadados/thumb/link em
    lote. Upsert em ad_insights e criativos; rehospeda a thumb. Retorna True em
    sucesso (False se o cliente não tem id_meta_ads ou se a coleta falhou)."""
    ad_account_id = cliente.id_meta_ads
    if not ad_account_id:
        log.warning("criativos_meta_sem_id", extra={"cliente": cliente.nome})
        return False

    cliente_id = cliente.id
    try:
        linhas = _meta_insights_diarios(ad_account_id, since, until)
    except Exception:
        log.exception("criativos_meta_insights_falhou", extra={"cliente": cliente.nome})
        return False

    if not linhas:
        log.info("criativos_meta_sem_dados", extra={"cliente": cliente.nome})
        return True

    ad_ids = sorted({l["ad_id"] for l in linhas})
    session = session_factory()
    own = session_factory is SessionLocal
    try:
        # 1) Grava o fato (ad_insights) e o esqueleto da dimensão (criativos).
        for l in linhas:
            upsert_ad_insight(
                session,
                cliente_id=cliente_id,
                rede=RedeAnuncio.META,
                ad_id=l["ad_id"],
                dia=l["dia"],
                investimento=l["investimento"],
                faturamento=l["faturamento"],
                conversoes=l["conversoes"],
                leads=None,
                impressoes=l["impressoes"],
                clicks=l["clicks"],
                video_3s=l["video_3s"],
                reach=l["reach"],
            )
            upsert_criativo(
                session,
                cliente_id=cliente_id,
                rede=RedeAnuncio.META,
                ad_id=l["ad_id"],
                nome=l["ad_name"],
                tipo=None,
                preview_link=None,
                dia=l["dia"],
            )
        session.commit()

        # 2) Metadados em lote (nome/tipo/preview/imagem) + thumb.
        try:
            metadados = _meta_metadados_lote(ad_ids)
        except Exception:
            log.exception("criativos_meta_metadados_falhou", extra={"cliente": cliente.nome})
            metadados = {}

        for ad_id in ad_ids:
            meta = metadados.get(ad_id) or {}
            upsert_criativo(
                session,
                cliente_id=cliente_id,
                rede=RedeAnuncio.META,
                ad_id=ad_id,
                nome=meta.get("nome"),
                tipo=meta.get("tipo"),
                preview_link=meta.get("preview_link"),
                dia=until,
            )
            session.flush()
            criativo = session.scalar(
                select(Criativo).where(
                    Criativo.cliente_id == cliente_id,
                    Criativo.rede == RedeAnuncio.META,
                    Criativo.ad_id == ad_id,
                )
            )
            imagem_url = meta.get("imagem_url")
            if not imagem_url:
                criativo.thumb_status = ThumbStatus.SEM_IMAGEM
                continue
            try:
                conteudo, mime = fetch_e_redimensionar(imagem_url, lado_max=320)
                _gravar_thumb(session, criativo.id, conteudo, mime)
                criativo.thumb_status = ThumbStatus.OK
            except Exception:
                log.exception("criativos_meta_thumb_falhou",
                              extra={"cliente": cliente.nome, "ad_id": ad_id})
                criativo.thumb_status = ThumbStatus.ERRO
        session.commit()
        return True
    except Exception:
        session.rollback()
        log.exception("criativos_meta_falhou", extra={"cliente": cliente.nome})
        return False
    finally:
        if own:
            session.close()


def _janela_backfill(backfill_meses: int, hoje: date) -> tuple[date, date]:
    until = hoje
    # aproxima meses por 30 dias (suficiente para a janela de backfill)
    since = hoje - timedelta(days=30 * backfill_meses)
    return since, until


def _janela_incremental(hoje: date) -> tuple[date, date]:
    ontem = hoje - timedelta(days=1)
    return ontem - timedelta(days=RETROACAO_DIAS), ontem


def run_collect_criativos(
    backfill_meses: int | None = None,
    incremental: bool = False,
    today: date | None = None,
) -> dict:
    """Entrypoint. backfill_meses=6 → janela últimos ~6 meses; incremental=True →
    ontem + RETROACAO_DIAS de retroação. Exatamente um modo (XOR). Coleta os
    clientes ativos com id_meta_ads em paralelo. Retorna {ok, fail, total}."""
    if (backfill_meses is None) == (not incremental):
        raise ValueError("Escolha exatamente um modo: backfill_meses XOR incremental")

    hoje = today or date.today()
    if incremental:
        since, until = _janela_incremental(hoje)
    else:
        since, until = _janela_backfill(backfill_meses, hoje)

    settings = get_settings()
    try:
        with advisory_lock(engine, "etl:criativos:run", blocking=False):
            with SessionLocal() as session:
                clientes = session.scalars(
                    select(Cliente).where(
                        Cliente.ativo == true(),
                        Cliente.id_meta_ads.isnot(None),
                    )
                ).all()
                clientes_ids = [c.id for c in clientes]

            ok = 0
            fail = 0

            def _processa(cliente_id: uuid.UUID) -> bool:
                with SessionLocal() as s:
                    cliente = s.get(Cliente, cliente_id)
                    return coletar_criativos_meta(
                        cliente, since, until, session_factory=SessionLocal
                    )

            with ThreadPoolExecutor(max_workers=settings.etl_threads) as pool:
                futures = {pool.submit(_processa, cid): cid for cid in clientes_ids}
                for f in as_completed(futures):
                    if f.result():
                        ok += 1
                    else:
                        fail += 1

            resumo = {"ok": ok, "fail": fail, "total": len(clientes_ids)}
            log.info("criativos_finalizado", extra=resumo)
            return resumo
    except LockTaken:
        log.warning("criativos_skip_lock_ocupado")
        return {"skipped": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta de criativos (Meta ad-level)")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--backfill-meses", type=int, dest="backfill_meses")
    grupo.add_argument("--incremental", action="store_true")
    args = parser.parse_args()
    resumo = run_collect_criativos(
        backfill_meses=args.backfill_meses, incremental=args.incremental
    )
    log.info("criativos_cli_resumo", extra=resumo)
    print(resumo)


if __name__ == "__main__":
    main()

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

# Campo de vídeo que historicamente quebra a request inteira quando inválido
# para a versão da API. Mantido isolado para o fallback de resiliência abaixo.
_VIDEO_FIELD = "video_play_actions"

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
    primeiro_dia: date,
    ultimo_dia: date,
    thumb_status: ThumbStatus | None = None,
) -> Criativo:
    """Upsert idempotente da dimensão (constraint uq_criativo_cliente_rede_ad).
    No conflito: atualiza nome/tipo/preview_link, expande primeiro_dia (LEAST)
    e ultimo_dia (GREATEST). Se thumb_status for fornecido, também o atualiza;
    caso contrário PRESERVA o valor existente (gerenciado pela coleta de thumb).
    Retorna a instância Criativo (com id preenchido)."""
    payload: dict = dict(
        cliente_id=cliente_id,
        rede=rede,
        ad_id=ad_id,
        nome=nome,
        tipo=tipo,
        preview_link=preview_link,
        primeiro_dia=primeiro_dia,
        ultimo_dia=ultimo_dia,
    )
    if thumb_status is not None:
        payload["thumb_status"] = thumb_status

    stmt = insert(Criativo).values(**payload)
    col = Criativo.__table__.c
    on_conflict_set: dict = {
        "nome": stmt.excluded.nome,
        "tipo": stmt.excluded.tipo,
        "preview_link": stmt.excluded.preview_link,
        "primeiro_dia": func.least(col.primeiro_dia, stmt.excluded.primeiro_dia),
        "ultimo_dia": func.greatest(col.ultimo_dia, stmt.excluded.ultimo_dia),
    }
    if thumb_status is not None:
        on_conflict_set["thumb_status"] = stmt.excluded.thumb_status
    stmt = stmt.on_conflict_do_update(
        constraint="uq_criativo_cliente_rede_ad",
        set_=on_conflict_set,
    )
    stmt = stmt.returning(Criativo)
    return session.scalars(stmt).one()


def _get_google_ads_service():
    """Wrapper para permitir mock em testes (espelha etl.collect._get_handler)."""
    client = _build_google_ads_client()
    return client.get_service("GoogleAdsService")


_GOOGLE_AD_FIELDS = (
    "ad_group_ad.ad.id",
    "ad_group_ad.ad.name",
    "ad_group_ad.ad.type",
    "ad_group_ad.ad_group",
    "ad_group_ad.ad.image_ad.image_url",
    "segments.date",
    "metrics.cost_micros",
    "metrics.conversions",
    "metrics.conversions_value",
    "metrics.impressions",
    "metrics.clicks",
)


def _build_google_query(since: date, until: date) -> str:
    campos = ", ".join(_GOOGLE_AD_FIELDS)
    return (
        f"SELECT {campos} "
        "FROM ad_group_ad "
        f"WHERE segments.date BETWEEN '{since.isoformat()}' AND '{until.isoformat()}'"
    )


def _google_deep_link(*, customer_id: str, ad_group_id: str | None, ad_id: str) -> str | None:
    """Deep-link para o anúncio no Google Ads UI. None quando não construível."""
    if not ad_group_id:
        return None
    return (
        f"https://ads.google.com/aw/ads?ocid={customer_id}"
        f"&__e={ad_id}&adGroupId={ad_group_id}"
    )


# Tipos de anúncio Google que carregam imagem própria via image_ad.image_url.
_GOOGLE_IMAGE_AD_TYPES = {"IMAGE_AD"}


def _google_thumb_url(ad) -> str | None:
    """URL da imagem do anúncio, ou None (search/sem imagem própria).

    `ad` é o objeto `ad_group_ad.ad` retornado pelo google-ads. `ad.type_.name`
    é a string do enum (ex.: 'IMAGE_AD', 'EXPANDED_TEXT_AD', 'RESPONSIVE_DISPLAY_AD').
    Nesta fase só image ads expoem imagem diretamente; responsive/video (cujos
    assets exigem segunda chamada a Asset API) e search/text -> None -> SEM_IMAGEM,
    conforme a limitacao de plataforma registrada no spec.
    """
    tipo = getattr(getattr(ad, "type_", None), "name", "") or ""
    if tipo in _GOOGLE_IMAGE_AD_TYPES:
        url = getattr(getattr(ad, "image_ad", None), "image_url", "") or ""
        return url or None
    return None


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
            "actions,action_values,video_play_actions"
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
        try:
            resp = httpx.get(next_url, params=next_params, timeout=TIMEOUT,
                             follow_redirects=True)
            resp.raise_for_status()
        except httpx.HTTPStatusError as err:
            # Resiliência: se o campo de vídeo é inválido p/ a versão da API a
            # request inteira retorna 400. Repete UMA vez sem o campo para que
            # os criativos continuem populando (video_3s vira None).
            fields = (next_params or {}).get("fields", "")
            if (err.response.status_code == 400 and _VIDEO_FIELD in fields):
                log.warning("Meta insights 400 com video field, retry sem video: %s",
                            err.response.text)
                retry_params = dict(next_params or {})
                partes = [f for f in fields.split(",") if f and f != _VIDEO_FIELD]
                retry_params["fields"] = ",".join(partes)
                resp = httpx.get(next_url, params=retry_params, timeout=TIMEOUT,
                                 follow_redirects=True)
                resp.raise_for_status()
            else:
                raise
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
                primeiro_dia=l["dia"],
                ultimo_dia=l["dia"],
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
                primeiro_dia=until,
                ultimo_dia=until,
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


def coletar_criativos_google(
    cliente: Cliente,
    since: date,
    until: date,
    session_factory: Callable[[], Session] = SessionLocal,
) -> bool:
    """Coleta ad_group_ad com segments.date via GAQL + thumb + deep-link.
    Search ads -> thumb_status = SEM_IMAGEM. Faz upsert em ad_insights e
    criativos (rede=GOOGLE). Retorna True em sucesso, False em falha de API."""
    customer_id = getattr(cliente, "id_google_ads", None)
    if not customer_id or customer_id == "0":
        log.info("collect_criativos_google skip sem id: %s", cliente.nome)
        return True

    from decimal import Decimal

    try:
        service = _get_google_ads_service()
    except Exception:
        log.exception("collect_criativos_google auth falhou (%s)", cliente.nome)
        return False

    query = _build_google_query(since, until)
    try:
        response = service.search(customer_id=str(customer_id), query=query)
        rows = list(response)
    except GoogleAdsException:
        log.exception("collect_criativos_google GAQL falhou (%s)", cliente.nome)
        return False

    # Agrega por (ad_id, dia); guarda metadados por ad_id.
    insights: dict[tuple[str, date], dict] = {}
    metas: dict[str, dict] = {}
    for row in rows:
        ad = row.ad_group_ad.ad
        ad_id = str(ad.id)
        dia = date.fromisoformat(str(row.segments.date))
        acc = insights.setdefault(
            (ad_id, dia),
            {"investimento": Decimal("0"), "faturamento": Decimal("0"),
             "conversoes": Decimal("0"), "impressoes": 0, "clicks": 0},
        )
        acc["investimento"] += Decimal(row.metrics.cost_micros or 0) / Decimal(1_000_000)
        acc["faturamento"] += Decimal(str(row.metrics.conversions_value or 0))
        acc["conversoes"] += Decimal(str(row.metrics.conversions or 0))
        acc["impressoes"] += int(row.metrics.impressions or 0)
        acc["clicks"] += int(row.metrics.clicks or 0)

        ad_group_path = row.ad_group_ad.ad_group
        ad_group_id = str(ad_group_path).rsplit("/", 1)[-1] if ad_group_path else None
        meta = metas.setdefault(
            ad_id,
            {"nome": ad.name or None,
             "tipo": getattr(getattr(ad, "type_", None), "name", None),
             "thumb_url": _google_thumb_url(ad),
             "ad_group_id": ad_group_id,
             "primeiro_dia": dia, "ultimo_dia": dia},
        )
        meta["primeiro_dia"] = min(meta["primeiro_dia"], dia)
        meta["ultimo_dia"] = max(meta["ultimo_dia"], dia)

    session = session_factory()
    own_session = session_factory is SessionLocal
    try:
        for (ad_id, dia), v in insights.items():
            upsert_ad_insight(
                session,
                cliente_id=cliente.id,
                rede=RedeAnuncio.GOOGLE,
                ad_id=ad_id,
                dia=dia,
                investimento=v["investimento"],
                faturamento=v["faturamento"],
                conversoes=v["conversoes"],
                leads=None,
                impressoes=v["impressoes"],
                clicks=v["clicks"],
                video_3s=None,
                reach=None,
            )

        for ad_id, meta in metas.items():
            thumb_url = meta["thumb_url"]
            if thumb_url:
                try:
                    conteudo, mime = fetch_e_redimensionar(thumb_url, lado_max=320)
                    thumb_status = ThumbStatus.OK
                except Exception:
                    log.exception(
                        "collect_criativos_google thumb falhou (%s ad_id=%s)",
                        cliente.nome, ad_id,
                    )
                    conteudo, mime, thumb_status = None, None, ThumbStatus.ERRO
            else:
                conteudo, mime, thumb_status = None, None, ThumbStatus.SEM_IMAGEM

            preview_link = _google_deep_link(
                customer_id=str(customer_id),
                ad_group_id=meta["ad_group_id"],
                ad_id=ad_id,
            )
            criativo = upsert_criativo(
                session,
                cliente_id=cliente.id,
                rede=RedeAnuncio.GOOGLE,
                ad_id=ad_id,
                nome=meta["nome"],
                tipo=meta["tipo"],
                preview_link=preview_link,
                thumb_status=thumb_status,
                primeiro_dia=meta["primeiro_dia"],
                ultimo_dia=meta["ultimo_dia"],
            )
            if thumb_status == ThumbStatus.OK and conteudo is not None:
                session.merge(
                    CriativoThumb(criativo_id=criativo.id, conteudo=conteudo, mime=mime)
                )

        session.commit()
    finally:
        if own_session:
            session.close()

    log.info(
        "collect_criativos_google ok (%s): ads=%d dias=%d",
        cliente.nome, len(metas), len(insights),
    )
    return True


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
    clientes ativos com id_meta_ads ou id_google_ads em paralelo (Meta + Google).
    Retorna {ok, fail, total}."""
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
                        (Cliente.id_meta_ads.isnot(None)) | (Cliente.id_google_ads.isnot(None)),
                    )
                ).all()

            ok = 0
            fail = 0
            with ThreadPoolExecutor(max_workers=settings.etl_threads) as pool:
                futures = []
                for cliente in clientes:
                    if cliente.id_meta_ads:
                        futures.append(pool.submit(coletar_criativos_meta, cliente, since, until))
                    if cliente.id_google_ads and cliente.id_google_ads != "0":
                        futures.append(pool.submit(coletar_criativos_google, cliente, since, until))
                for f in as_completed(futures):
                    if f.result():
                        ok += 1
                    else:
                        fail += 1

            resumo = {"ok": ok, "fail": fail, "total": len(futures)}
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

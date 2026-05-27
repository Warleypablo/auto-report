from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any, Literal

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.auth import require_auth
from app_settings import get_settings
from db import get_session
from models import Cliente, Insight, Usuario, UsuarioCliente
from models.snapshot import Frequencia, Snapshot

router = APIRouter(prefix="/turbomax", tags=["turbomax"])
_log = logging.getLogger(__name__)


# ─── Pydantic models ─────────────────────────────────────────────────────────

class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn]
    cliente_slug: str = ""


class ChatResponse(BaseModel):
    reply: str


# ─── System Prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Você é TurboMax, especialista máximo em performance digital da Turbo Partners.
Domina Meta Ads e Google Ads no nível mais técnico. Responde sempre em português,
com dados reais quando disponíveis.

EXPERTISE META ADS:
- Estrutura de campanhas: CBO vs ABO, Campaign Budget Optimization
- Audiências: Lookalike (1–10%), Retargeting (visitantes, compradores), Broad, Interest
- Attribution windows: 1d_click, 7d_click, 1d_view — impacto direto no ROAS reportado
- Criativos: UGC, Carrossel, Reels, Image Ads — hooks, CTR benchmark > 2%
- Diagnóstico: fadiga de audiência (CTR caindo + CPM subindo), frequency > 3.5
- Meta Advantage+ Shopping Campaigns (ASC) vs campanhas manuais
- Pixel events: Purchase, AddToCart, InitiateCheckout — qualidade do sinal de conversão

EXPERTISE GOOGLE ADS:
- Estratégias de lance: Target ROAS (tROAS), Maximize Conversions, tCPA — quando usar cada
- Quality Score: componentes (CTR esperado, relevância, landing page) — impacto no CPC
- Performance Max: como funciona, quando usar, como interpretar asset groups
- Search Impression Share (SIS): perdido por orçamento vs rank
- Brand vs Non-brand: diferença de custo, ROAS inflado por brand
- Smart Bidding: período de aprendizado (2 semanas, 50 conversões)

CONTEXTO TURBO PARTNERS:
- Categorias de clientes: E-commerce (ROAS ≥ 3.0 é referência), Lead Com Site, \
Lead Sem Site (CPL como métrica principal)
- Métricas disponíveis: faturamento, investimento, ROAS, CPA, leads, vendas (mensais)
- Sinais: roas_queda (>20%), faturamento_queda (>25%), roas_brand_inflado, \
oportunidade_escala, cpl_vs_media
- Dados de criativo disponíveis: hook_rate (% de impressões com 3s de vídeo), \
frequency por anúncio, CTR por anúncio, ROAS por anúncio, CPM por anúncio
- Benchmarks criativo Meta: hook_rate > 20% = bom, < 10% = problema no início do vídeo; \
CTR > 2% = bom; frequency > 3.5 no mesmo anúncio = fadiga; CPM subindo + CTR caindo = saturação
- Para top criativos Meta use buscar_anuncios_meta; para criativos Google use buscar_anuncios_google

REGRAS:
- Sempre use ferramentas para buscar dados antes de responder sobre clientes específicos
- Quando comparar clientes ou campanhas, use tabelas markdown
- Nunca invente números — se não tiver dado, diga que não tem e sugira como obter
- Se o usuário perguntar sobre "bom" ou "ruim", compare com benchmarks da carteira
- Gestores veem apenas seus clientes atribuídos

{user_context}"""


# ─── Tool definitions ─────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "listar_clientes",
        "description": "Lista todos os clientes acessíveis ao gestor com métricas do mês mais recente.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_metricas_cliente",
        "description": (
            "Retorna métricas detalhadas de um cliente num mês específico "
            "(ROAS, faturamento, investimento, leads, vendas, breakdown por canal Meta/Google)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "mes": {
                    "type": "string",
                    "description": "Mês no formato YYYY-MM. Se omitido, usa o mais recente.",
                },
            },
            "required": ["slug"],
        },
    },
    {
        "name": "get_historico_cliente",
        "description": "Retorna os últimos N meses de snapshots de um cliente para análise de tendência.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "n_meses": {
                    "type": "integer",
                    "description": "Número de meses (1–24). Padrão: 6.",
                },
            },
            "required": ["slug"],
        },
    },
    {
        "name": "get_sinais_cliente",
        "description": "Retorna sinais de inteligência detectados e narrativa gerada para um cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "mes": {
                    "type": "string",
                    "description": "Mês no formato YYYY-MM. Se omitido, usa o mais recente.",
                },
            },
            "required": ["slug"],
        },
    },
    {
        "name": "comparar_clientes",
        "description": (
            "Compara múltiplos clientes (ou toda a carteira) numa métrica, "
            "com ranking e média da carteira."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slugs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Lista de slugs para comparar. "
                        "Se vazio ou omitido, compara todos os clientes do gestor."
                    ),
                },
                "metrica": {
                    "type": "string",
                    "enum": ["roas", "faturamento", "investimento", "cpa", "leads", "vendas"],
                    "description": "Métrica para comparação",
                },
                "mes": {
                    "type": "string",
                    "description": "Mês no formato YYYY-MM. Se omitido, usa o mais recente.",
                },
            },
            "required": ["metrica"],
        },
    },
    {
        "name": "buscar_campanhas_meta",
        "description": "Busca campanhas ao vivo no Meta Ads para um cliente num período.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "date_start": {"type": "string", "description": "Data início YYYY-MM-DD"},
                "date_end": {"type": "string", "description": "Data fim YYYY-MM-DD"},
            },
            "required": ["slug", "date_start", "date_end"],
        },
    },
    {
        "name": "buscar_campanhas_google",
        "description": "Busca campanhas ao vivo no Google Ads para um cliente num período.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "date_start": {"type": "string", "description": "Data início YYYY-MM-DD"},
                "date_end": {"type": "string", "description": "Data fim YYYY-MM-DD"},
            },
            "required": ["slug", "date_start", "date_end"],
        },
    },
    {
        "name": "buscar_anuncios_meta",
        "description": (
            "Busca anúncios individuais no Meta Ads para um cliente num período. "
            "Retorna métricas por criativo: CTR, CPM, hook rate (retenção de 3s), "
            "frequency, purchases e ROAS por anúncio. Use para identificar quais "
            "criativos estão performando melhor ou apresentando fadiga."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "date_start": {"type": "string", "description": "Data início YYYY-MM-DD"},
                "date_end": {"type": "string", "description": "Data fim YYYY-MM-DD"},
            },
            "required": ["slug", "date_start", "date_end"],
        },
    },
    {
        "name": "buscar_anuncios_google",
        "description": (
            "Busca anúncios individuais no Google Ads para um cliente num período. "
            "Retorna métricas por ad: CTR, CPC, conversões, ROAS e ad group. "
            "Use para identificar quais anúncios de texto/display convertem melhor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {"type": "string", "description": "Slug do cliente"},
                "date_start": {"type": "string", "description": "Data início YYYY-MM-DD"},
                "date_end": {"type": "string", "description": "Data fim YYYY-MM-DD"},
            },
            "required": ["slug", "date_start", "date_end"],
        },
    },
]


# ─── Access control helper ────────────────────────────────────────────────────

def _check_acesso_cliente(slug: str, user: Usuario, session: Session) -> Cliente:
    """Retorna o cliente se o gestor tem acesso; levanta ValueError se não."""
    cliente = session.scalar(select(Cliente).where(Cliente.slug == slug))
    if cliente is None:
        raise ValueError(f"Cliente '{slug}' não encontrado")
    if not user.is_admin:
        atribuido = session.scalar(
            select(UsuarioCliente).where(
                UsuarioCliente.usuario_id == user.id,
                UsuarioCliente.cliente_id == cliente.id,
            )
        )
        if atribuido is None:
            raise ValueError(f"Você não tem acesso ao cliente '{slug}'")
    return cliente


# ─── Core client helper (Planilha Central) ────────────────────────────────────

def _get_cliente_core(slug: str):
    """Busca o objeto core do cliente na Planilha Central pelo slug. Retorna None se não encontrar."""
    from etl.cliente_publico import slugify
    from etl.sync_planilha import fetch_clientes_tolerante

    for c in fetch_clientes_tolerante():
        if slugify(c.nome) == slug:
            return c
    return None


# ─── DB tools ─────────────────────────────────────────────────────────────────

def _listar_clientes(user: Usuario, session: Session) -> list[dict]:
    if user.is_admin:
        clientes = session.scalars(select(Cliente)).all()
    else:
        clientes = session.scalars(
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(UsuarioCliente.usuario_id == user.id)
        ).all()

    result = []
    for c in clientes:
        snap = session.scalar(
            select(Snapshot)
            .where(Snapshot.cliente_id == c.id, Snapshot.frequencia == Frequencia.MENSAL)
            .order_by(Snapshot.periodo_inicio.desc())
            .limit(1)
        )
        result.append({
            "slug": c.slug,
            "nome": c.nome,
            "categoria": c.categoria.value if c.categoria else None,
            "ativo": c.ativo,
            "ultimo_snapshot": {
                "mes": snap.periodo_inicio.strftime("%Y-%m"),
                "roas": float(snap.roas) if snap.roas else None,
                "faturamento": float(snap.faturamento) if snap.faturamento else None,
                "investimento": float(snap.investimento) if snap.investimento else None,
                "leads": snap.leads,
                "vendas": snap.vendas,
            } if snap else None,
        })
    return result


def _get_metricas_cliente(
    slug: str, mes: str | None, user: Usuario, session: Session
) -> dict:
    cliente = _check_acesso_cliente(slug, user, session)

    filtros = [Snapshot.cliente_id == cliente.id, Snapshot.frequencia == Frequencia.MENSAL]
    if mes:
        ano, mes_num = int(mes[:4]), int(mes[5:7])
        filtros.append(Snapshot.periodo_inicio == date(ano, mes_num, 1))

    snap = session.scalar(
        select(Snapshot).where(*filtros).order_by(Snapshot.periodo_inicio.desc()).limit(1)
    )
    if not snap:
        return {"erro": f"Nenhum snapshot para '{slug}'" + (f" em {mes}" if mes else "")}

    det = snap.metricas_detalhadas or {}
    meta = det.get("meta", {})
    google = det.get("google", {})

    return {
        "cliente": cliente.nome,
        "slug": slug,
        "categoria": cliente.categoria.value if cliente.categoria else None,
        "mes": snap.periodo_inicio.strftime("%Y-%m"),
        "roas": float(snap.roas) if snap.roas else None,
        "roas_var_pct": float(snap.roas_var_pct) if snap.roas_var_pct else None,
        "faturamento": float(snap.faturamento) if snap.faturamento else None,
        "faturamento_var_pct": float(snap.faturamento_var_pct) if snap.faturamento_var_pct else None,
        "investimento": float(snap.investimento) if snap.investimento else None,
        "cpa": float(snap.cpa) if snap.cpa else None,
        "leads": snap.leads,
        "vendas": snap.vendas,
        "meta": {k: float(v) if isinstance(v, (int, float)) else v for k, v in meta.items()} if meta else None,
        "google": {k: float(v) if isinstance(v, (int, float)) else v for k, v in google.items()} if google else None,
    }


def _get_historico_cliente(
    slug: str, n_meses: int, user: Usuario, session: Session
) -> list[dict]:
    cliente = _check_acesso_cliente(slug, user, session)
    n_meses = min(max(n_meses, 1), 24)

    snaps = session.scalars(
        select(Snapshot)
        .where(Snapshot.cliente_id == cliente.id, Snapshot.frequencia == Frequencia.MENSAL)
        .order_by(Snapshot.periodo_inicio.desc())
        .limit(n_meses)
    ).all()

    return [
        {
            "mes": s.periodo_inicio.strftime("%Y-%m"),
            "roas": float(s.roas) if s.roas else None,
            "roas_var_pct": float(s.roas_var_pct) if s.roas_var_pct else None,
            "faturamento": float(s.faturamento) if s.faturamento else None,
            "faturamento_var_pct": float(s.faturamento_var_pct) if s.faturamento_var_pct else None,
            "investimento": float(s.investimento) if s.investimento else None,
            "cpa": float(s.cpa) if s.cpa else None,
            "leads": s.leads,
            "vendas": s.vendas,
        }
        for s in reversed(snaps)
    ]


def _get_sinais_cliente(
    slug: str, mes: str | None, user: Usuario, session: Session
) -> dict:
    cliente = _check_acesso_cliente(slug, user, session)

    filtros = [Insight.cliente_id == cliente.id]
    if mes:
        filtros.append(Insight.mes == mes)

    insight = session.scalar(
        select(Insight).where(*filtros).order_by(Insight.mes.desc()).limit(1)
    )
    if not insight:
        return {"erro": f"Nenhum insight para '{slug}'" + (f" em {mes}" if mes else "")}

    return {
        "cliente": cliente.nome,
        "slug": slug,
        "mes": insight.mes,
        "sinais": insight.sinais or [],
        "narrativa": insight.narrativa,
    }


def _comparar_clientes(
    slugs: list[str] | None,
    metrica: str,
    mes: str | None,
    user: Usuario,
    session: Session,
) -> dict:
    if slugs:
        clientes = [_check_acesso_cliente(s, user, session) for s in slugs]
    elif user.is_admin:
        clientes = session.scalars(select(Cliente)).all()
    else:
        clientes = session.scalars(
            select(Cliente)
            .join(UsuarioCliente, UsuarioCliente.cliente_id == Cliente.id)
            .where(UsuarioCliente.usuario_id == user.id)
        ).all()

    campo = getattr(Snapshot, metrica, None)
    if campo is None:
        return {"erro": f"Métrica '{metrica}' inválida"}

    filtros = [Snapshot.frequencia == Frequencia.MENSAL]
    if mes:
        ano, mes_num = int(mes[:4]), int(mes[5:7])
        filtros.append(Snapshot.periodo_inicio == date(ano, mes_num, 1))

    ranking = []
    valores: list[float] = []
    for c in clientes:
        snap = session.scalar(
            select(Snapshot)
            .where(Snapshot.cliente_id == c.id, *filtros)
            .order_by(Snapshot.periodo_inicio.desc())
            .limit(1)
        )
        if snap:
            val = getattr(snap, metrica)
            var = getattr(snap, f"{metrica}_var_pct", None)
            if val is not None:
                fval = float(val)
                valores.append(fval)
                ranking.append({
                    "slug": c.slug,
                    "nome": c.nome,
                    "valor": fval,
                    "var_pct": float(var) if var is not None else None,
                })

    ranking.sort(key=lambda x: x["valor"], reverse=True)
    media = round(sum(valores) / len(valores), 4) if valores else None

    return {
        "metrica": metrica,
        "mes": mes or "mais recente por cliente",
        "ranking": ranking,
        "media_carteira": media,
    }


# ─── External API tools ───────────────────────────────────────────────────────

_META_API_VERSION = "v23.0"
_META_CAMPAIGN_FIELDS = (
    "campaign_id,campaign_name,spend,impressions,clicks,actions,action_values"
)
_META_AD_FIELDS = (
    "ad_id,ad_name,adset_name,campaign_name,"
    "spend,impressions,clicks,reach,frequency,"
    "actions,action_values,video_p3_watched_actions"
)


def _buscar_campanhas_meta(
    slug: str, date_start: str, date_end: str, user: Usuario, session: Session
) -> dict:
    _check_acesso_cliente(slug, user, session)

    cliente_core = _get_cliente_core(slug)
    if cliente_core is None:
        return {"erro": f"Cliente '{slug}' não encontrado na Planilha Central"}

    ad_account_id = getattr(cliente_core, "id_meta_ads", None)
    if not ad_account_id:
        return {"erro": f"Cliente '{slug}' não tem ID Meta Ads configurado"}

    from config.settings import ACCESS_TOKEN_META_SYSTEM  # noqa: PLC0415

    raw = str(ad_account_id)
    acct_path = f"act_{raw.removeprefix('act_')}"
    url = f"https://graph.facebook.com/{_META_API_VERSION}/{acct_path}/insights"
    params = {
        "level": "campaign",
        "time_range": json.dumps({"since": date_start, "until": date_end}, separators=(",", ":")),
        "time_increment": "all_days",
        "fields": _META_CAMPAIGN_FIELDS,
        "access_token": ACCESS_TOKEN_META_SYSTEM,
        "limit": 25,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        _log.warning("Meta Ads API falhou para %s: %s", slug, exc)
        return {"erro": f"Falha ao acessar Meta Ads: {exc}"}

    campanhas = []
    for c in resp.json().get("data", []):
        spend = float(c.get("spend") or 0)
        impressions = int(c.get("impressions") or 0)
        clicks = int(c.get("clicks") or 0)
        actions = {a["action_type"]: float(a["value"]) for a in c.get("actions") or []}
        action_values = {a["action_type"]: float(a["value"]) for a in c.get("action_values") or []}
        purchases = actions.get("purchase", actions.get("offsite_conversion.fb_pixel_purchase", 0))
        purchase_value = action_values.get(
            "purchase", action_values.get("offsite_conversion.fb_pixel_purchase", 0)
        )
        campanhas.append({
            "id": c.get("campaign_id"),
            "nome": c.get("campaign_name"),
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions * 100, 2) if impressions else 0,
            "purchases": int(purchases),
            "purchase_roas": round(purchase_value / spend, 2) if spend else 0,
            "cpm": round(spend / impressions * 1000, 2) if impressions else 0,
        })

    campanhas.sort(key=lambda x: x["spend"], reverse=True)
    return {
        "cliente": slug,
        "periodo": {"inicio": date_start, "fim": date_end},
        "campanhas": campanhas,
    }


def _buscar_anuncios_meta(
    slug: str, date_start: str, date_end: str, user: Usuario, session: Session
) -> dict:
    _check_acesso_cliente(slug, user, session)

    cliente_core = _get_cliente_core(slug)
    if cliente_core is None:
        return {"erro": f"Cliente '{slug}' não encontrado na Planilha Central"}

    ad_account_id = getattr(cliente_core, "id_meta_ads", None)
    if not ad_account_id:
        return {"erro": f"Cliente '{slug}' não tem ID Meta Ads configurado"}

    from config.settings import ACCESS_TOKEN_META_SYSTEM  # noqa: PLC0415

    raw = str(ad_account_id)
    acct_path = f"act_{raw.removeprefix('act_')}"
    url = f"https://graph.facebook.com/{_META_API_VERSION}/{acct_path}/insights"
    params = {
        "level": "ad",
        "time_range": json.dumps({"since": date_start, "until": date_end}, separators=(",", ":")),
        "time_increment": "all_days",
        "fields": _META_AD_FIELDS,
        "access_token": ACCESS_TOKEN_META_SYSTEM,
        "limit": 50,
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        _log.warning("Meta Ads API (ad level) falhou para %s: %s", slug, exc)
        return {"erro": f"Falha ao acessar Meta Ads: {exc}"}

    anuncios = []
    for a in resp.json().get("data", []):
        spend = float(a.get("spend") or 0)
        impressions = int(a.get("impressions") or 0)
        clicks = int(a.get("clicks") or 0)
        frequency = float(a.get("frequency") or 0)

        actions = {x["action_type"]: float(x["value"]) for x in a.get("actions") or []}
        action_values = {x["action_type"]: float(x["value"]) for x in a.get("action_values") or []}
        video_p3 = {x["action_type"]: float(x["value"]) for x in a.get("video_p3_watched_actions") or []}
        video_3s = video_p3.get("video_view", 0.0)

        purchases = actions.get("purchase", actions.get("offsite_conversion.fb_pixel_purchase", 0))
        purchase_value = action_values.get(
            "purchase", action_values.get("offsite_conversion.fb_pixel_purchase", 0)
        )

        anuncios.append({
            "id": a.get("ad_id"),
            "nome": a.get("ad_name"),
            "adset": a.get("adset_name"),
            "campanha": a.get("campaign_name"),
            "spend": spend,
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions * 100, 2) if impressions else 0,
            "cpm": round(spend / impressions * 1000, 2) if impressions else 0,
            "frequency": round(frequency, 2),
            "hook_rate": round(video_3s / impressions * 100, 2) if impressions else None,
            "purchases": int(purchases),
            "purchase_roas": round(purchase_value / spend, 2) if spend else 0,
        })

    anuncios.sort(key=lambda x: x["spend"], reverse=True)
    return {
        "cliente": slug,
        "periodo": {"inicio": date_start, "fim": date_end},
        "anuncios": anuncios,
    }


def _buscar_campanhas_google(
    slug: str, date_start: str, date_end: str, user: Usuario, session: Session
) -> dict:
    _check_acesso_cliente(slug, user, session)

    cliente_core = _get_cliente_core(slug)
    if cliente_core is None:
        return {"erro": f"Cliente '{slug}' não encontrado na Planilha Central"}

    customer_id = str(getattr(cliente_core, "id_google_ads", "") or "").replace("-", "")
    if not customer_id or customer_id == "0":
        return {"erro": f"Cliente '{slug}' não tem ID Google Ads configurado"}

    for d in (date_start, date_end):
        if len(d) != 10 or d[4] != "-" or d[7] != "-" or not d.replace("-", "").isdigit():
            return {"erro": f"Formato de data inválido: '{d}'. Use YYYY-MM-DD."}

    from core.cred_manager import _build_google_ads_client  # noqa: PLC0415

    gaql = (
        "SELECT campaign.id, campaign.name, campaign.status, "
        "metrics.cost_micros, metrics.impressions, metrics.clicks, "
        "metrics.conversions, metrics.conversions_value "
        "FROM campaign "
        f"WHERE segments.date BETWEEN '{date_start}' AND '{date_end}' "
        "AND metrics.cost_micros > 0 "
        "ORDER BY metrics.cost_micros DESC "
        "LIMIT 25"
    )

    try:
        client = _build_google_ads_client()
        ga_service = client.get_service("GoogleAdsService")
        response = ga_service.search(customer_id=customer_id, query=gaql)
    except Exception as exc:
        _log.warning("Google Ads API falhou para %s: %s", slug, exc)
        return {"erro": f"Falha ao acessar Google Ads: {exc}"}

    campanhas = []
    for row in response:
        cost = row.metrics.cost_micros / 1_000_000
        conv = float(row.metrics.conversions or 0)
        conv_value = float(row.metrics.conversions_value or 0)
        campanhas.append({
            "id": str(row.campaign.id),
            "nome": row.campaign.name,
            "status": row.campaign.status.name,
            "spend": round(cost, 2),
            "impressions": int(row.metrics.impressions or 0),
            "clicks": int(row.metrics.clicks or 0),
            "conversions": round(conv, 1),
            "conv_value": round(conv_value, 2),
            "roas": round(conv_value / cost, 2) if cost else 0,
            "cpc": round(cost / row.metrics.clicks, 2) if row.metrics.clicks else 0,
        })

    return {
        "cliente": slug,
        "periodo": {"inicio": date_start, "fim": date_end},
        "campanhas": campanhas,
    }


def _buscar_anuncios_google(
    slug: str, date_start: str, date_end: str, user: Usuario, session: Session
) -> dict:
    _check_acesso_cliente(slug, user, session)

    cliente_core = _get_cliente_core(slug)
    if cliente_core is None:
        return {"erro": f"Cliente '{slug}' não encontrado na Planilha Central"}

    customer_id = str(getattr(cliente_core, "id_google_ads", "") or "").replace("-", "")
    if not customer_id or customer_id == "0":
        return {"erro": f"Cliente '{slug}' não tem ID Google Ads configurado"}

    for d in (date_start, date_end):
        if len(d) != 10 or d[4] != "-" or d[7] != "-" or not d.replace("-", "").isdigit():
            return {"erro": f"Formato de data inválido: '{d}'. Use YYYY-MM-DD."}

    from core.cred_manager import _build_google_ads_client  # noqa: PLC0415

    gaql = (
        "SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, ad_group_ad.ad.type, "
        "ad_group.name, campaign.name, "
        "metrics.cost_micros, metrics.impressions, metrics.clicks, "
        "metrics.conversions, metrics.conversions_value "
        "FROM ad_group_ad "
        f"WHERE segments.date BETWEEN '{date_start}' AND '{date_end}' "
        "AND metrics.cost_micros > 0 "
        "ORDER BY metrics.cost_micros DESC "
        "LIMIT 50"
    )

    try:
        client = _build_google_ads_client()
        ga_service = client.get_service("GoogleAdsService")
        response = ga_service.search(customer_id=customer_id, query=gaql)
    except Exception as exc:
        _log.warning("Google Ads API (ad level) falhou para %s: %s", slug, exc)
        return {"erro": f"Falha ao acessar Google Ads: {exc}"}

    anuncios = []
    for row in response:
        cost = row.metrics.cost_micros / 1_000_000
        conv = float(row.metrics.conversions or 0)
        conv_value = float(row.metrics.conversions_value or 0)
        impressions = int(row.metrics.impressions or 0)
        clicks = int(row.metrics.clicks or 0)
        anuncios.append({
            "id": str(row.ad_group_ad.ad.id),
            "nome": row.ad_group_ad.ad.name,
            "tipo": getattr(row.ad_group_ad.ad.type_, "name", None),
            "ad_group": row.ad_group.name,
            "campanha": row.campaign.name,
            "spend": round(cost, 2),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": round(clicks / impressions * 100, 2) if impressions else 0,
            "cpc": round(cost / clicks, 2) if clicks else 0,
            "conversions": round(conv, 1),
            "conv_value": round(conv_value, 2),
            "roas": round(conv_value / cost, 2) if cost else 0,
        })

    return {
        "cliente": slug,
        "periodo": {"inicio": date_start, "fim": date_end},
        "anuncios": anuncios,
    }


# ─── Tool executor ────────────────────────────────────────────────────────────

def _execute_tool(
    name: str, tool_input: dict, user: Usuario, session: Session
) -> Any:
    """Mapeia nome de tool para função Python e executa. Retorna dict serializável."""
    if name == "listar_clientes":
        return _listar_clientes(user, session)
    if name == "get_metricas_cliente":
        return _get_metricas_cliente(
            tool_input["slug"], tool_input.get("mes"), user, session
        )
    if name == "get_historico_cliente":
        return _get_historico_cliente(
            tool_input["slug"], tool_input.get("n_meses", 6), user, session
        )
    if name == "get_sinais_cliente":
        return _get_sinais_cliente(
            tool_input["slug"], tool_input.get("mes"), user, session
        )
    if name == "comparar_clientes":
        return _comparar_clientes(
            tool_input.get("slugs"), tool_input["metrica"], tool_input.get("mes"),
            user, session,
        )
    if name == "buscar_campanhas_meta":
        return _buscar_campanhas_meta(
            tool_input["slug"], tool_input["date_start"], tool_input["date_end"],
            user, session,
        )
    if name == "buscar_campanhas_google":
        return _buscar_campanhas_google(
            tool_input["slug"], tool_input["date_start"], tool_input["date_end"],
            user, session,
        )
    if name == "buscar_anuncios_meta":
        return _buscar_anuncios_meta(
            tool_input["slug"], tool_input["date_start"], tool_input["date_end"],
            user, session,
        )
    if name == "buscar_anuncios_google":
        return _buscar_anuncios_google(
            tool_input["slug"], tool_input["date_start"], tool_input["date_end"],
            user, session,
        )
    return {"erro": f"Ferramenta '{name}' não reconhecida"}


# ─── Agent loop ───────────────────────────────────────────────────────────────

_MAX_ITERATIONS = 8


def _run_agent(
    messages: list[dict],
    user_context: str,
    user: Usuario,
    session: Session,
    api_key: str,
) -> str:
    import anthropic  # noqa: PLC0415

    client = anthropic.Anthropic(api_key=api_key)
    system = _SYSTEM_PROMPT.format(user_context=user_context)
    history = list(messages)
    response = None

    for _ in range(_MAX_ITERATIONS):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system,
            messages=history,
            tools=TOOLS,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        if response.stop_reason == "tool_use":
            history.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result = _execute_tool(block.name, block.input, user, session)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str, ensure_ascii=False),
                        })
                    except Exception as exc:
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "is_error": True,
                            "content": str(exc),
                        })
            history.append({"role": "user", "content": tool_results})
        else:
            break

    # Fallback: retorna último texto encontrado no histórico
    if response is not None:
        for block in getattr(response, "content", []):
            if hasattr(block, "text"):
                return block.text
    return "Não consegui processar sua solicitação. Por favor, tente novamente."


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    user: Usuario = Depends(require_auth),
    session: Session = Depends(get_session),
):
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(503, "Chave Anthropic não configurada")
    if not body.messages:
        raise HTTPException(400, "messages não pode ser vazio")
    if body.messages[-1].role != "user":
        raise HTTPException(400, "Última mensagem deve ser do usuário")

    # Monta contexto do usuário para o system prompt
    if user.is_admin:
        user_ctx = f"USUÁRIO: {user.email} (admin — acessa todos os clientes)"
    else:
        n = session.scalar(
            select(func.count(UsuarioCliente.cliente_id)).where(
                UsuarioCliente.usuario_id == user.id
            )
        ) or 0
        user_ctx = f"USUÁRIO: {user.email} — {n} cliente(s) atribuído(s)"

    if body.cliente_slug:
        try:
            _check_acesso_cliente(body.cliente_slug, user, session)
        except ValueError as exc:
            msg = str(exc)
            raise HTTPException(404 if "não encontrado" in msg else 403, detail=msg)
        user_ctx += f"\nCONTEXTO: conversa sobre o cliente '{body.cliente_slug}'"

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    reply = _run_agent(messages, user_ctx, user, session, settings.anthropic_api_key)

    return ChatResponse(reply=reply)

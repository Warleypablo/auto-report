from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

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
    role: str
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

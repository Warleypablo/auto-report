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

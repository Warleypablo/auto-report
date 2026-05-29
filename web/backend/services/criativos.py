from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import AdInsight, Cliente, Criativo, Usuario, UsuarioCliente
from models.cliente import Categoria
from schemas import CriativoAgregado

_REDE_MAP = {"meta": "META", "google": "GOOGLE"}


def _ratio(num: float | None, den: float | None) -> float | None:
    """Razão num/den; None quando num/den ausentes ou den <= 0."""
    if num is None or den is None or den <= 0:
        return None
    return float(num) / float(den)


def agregar_criativos(
    session: Session,
    *,
    de: date,
    ate: date,
    rede: str,
    categorias: list[str] | None,
    gestor: str | None,
    cliente_slug: str | None,
    fat_min: float | None,
    fat_max: float | None,
    inv_min: float | None,
    inv_max: float | None,
    cli_fat_min: float | None,
    cli_fat_max: float | None,
    cli_inv_min: float | None,
    cli_inv_max: float | None,
    order_by: str,
    limit: int,
    offset: int,
    user: Usuario,
) -> tuple[list[CriativoAgregado], int]:
    """Agrega ad_insights por (cliente_id, rede, ad_id) no range [de, ate].

    Somas no banco (GROUP BY); métricas derivadas em Python; ordenação e
    paginação após o cálculo. Escopo: admin = todos os Cliente.ativo;
    gestor = clientes vinculados via UsuarioCliente. Retorna (items, total)
    onde total = nº de grupos antes de limit/offset.
    """
    # Somas por anúncio
    base = (
        select(
            AdInsight.cliente_id.label("cliente_id"),
            AdInsight.rede.label("rede"),
            AdInsight.ad_id.label("ad_id"),
            func.sum(AdInsight.investimento).label("investimento"),
            func.sum(AdInsight.faturamento).label("faturamento"),
            func.sum(AdInsight.conversoes).label("conversoes"),
            func.sum(AdInsight.leads).label("leads"),
            func.sum(AdInsight.impressoes).label("impressoes"),
            func.sum(AdInsight.clicks).label("clicks"),
            func.sum(AdInsight.video_3s).label("video_3s"),
            func.sum(AdInsight.reach).label("reach"),
        )
        .join(Cliente, Cliente.id == AdInsight.cliente_id)
        .where(AdInsight.dia >= de, AdInsight.dia <= ate, Cliente.ativo.is_(True))
        .group_by(AdInsight.cliente_id, AdInsight.rede, AdInsight.ad_id)
    )

    # Escopo de acesso
    if not user.is_admin:
        cliente_ids = session.execute(
            select(UsuarioCliente.cliente_id).where(UsuarioCliente.usuario_id == user.id)
        ).scalars().all()
        base = base.where(AdInsight.cliente_id.in_(cliente_ids))

    rows = session.execute(base).all()

    # Metadados de criativos e clientes (carregados em lote)
    criativos = {
        (cr.cliente_id, cr.rede.value, cr.ad_id): cr
        for cr in session.execute(select(Criativo)).scalars().all()
    }
    clientes = {c.id: c for c in session.execute(select(Cliente)).scalars().all()}

    items: list[CriativoAgregado] = []
    for r in rows:
        cli = clientes.get(r.cliente_id)
        if cli is None:
            continue
        rede_str = r.rede.value.lower()
        cr = criativos.get((r.cliente_id, r.rede.value, r.ad_id))

        investimento = float(r.investimento) if r.investimento is not None else 0.0
        faturamento = float(r.faturamento) if r.faturamento is not None else 0.0
        conversoes = float(r.conversoes) if r.conversoes is not None else 0.0
        leads = int(r.leads) if r.leads is not None else None
        impressoes = int(r.impressoes) if r.impressoes is not None else 0
        clicks = int(r.clicks) if r.clicks is not None else 0
        video_3s = int(r.video_3s) if r.video_3s is not None else None
        reach = int(r.reach) if r.reach is not None else None

        items.append(CriativoAgregado(
            criativo_id=cr.id if cr is not None else uuid.uuid4(),
            cliente_slug=cli.slug,
            cliente_nome=cli.nome,
            categoria=cli.categoria.value,
            gestor_nome=cli.gestor,
            rede=rede_str,
            ad_id=r.ad_id,
            nome=cr.nome if cr is not None else None,
            tipo=cr.tipo if cr is not None else None,
            preview_link=cr.preview_link if cr is not None else None,
            thumb_url=None,  # preenchido na camada API
            thumb_status=cr.thumb_status.value if cr is not None else "pendente",
            investimento=investimento,
            faturamento=faturamento,
            roas=_ratio(faturamento, investimento),
            ctr=_ratio(clicks, impressoes),
            cpa=_ratio(investimento, conversoes),
            cpl=_ratio(investimento, leads),
            impressoes=impressoes,
            clicks=clicks,
            conversoes=conversoes,
            leads=leads,
            hook_rate=_ratio(video_3s, impressoes) if video_3s is not None else None,
            frequency=_ratio(impressoes, reach),
        ))

    total = len(items)

    _sort_key = {
        "roas": lambda it: (it.roas if it.roas is not None else -1.0),
        "faturamento": lambda it: it.faturamento,
        "investimento": lambda it: it.investimento,
    }[order_by]
    items.sort(key=_sort_key, reverse=True)

    items = items[offset:offset + limit]
    return items, total

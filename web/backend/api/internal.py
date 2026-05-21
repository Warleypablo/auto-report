import calendar
import re
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app_settings import Settings, get_settings
from db import get_session
from etl.collect import run_etl
from etl.sync_planilha import sync_clientes
from models import Cliente, Snapshot
from schemas import (
    ClienteListItem,
    ClientesListResponse,
    PeriodoDisponivel,
    PeriodosResponse,
)

router = APIRouter()

_MES_RE = re.compile(r"^(\d{4})-(\d{2})$")


def _mes_para_periodo(mes: str) -> tuple[date, date]:
    """Converte 'YYYY-MM' em (primeiro_dia, ultimo_dia) do mês."""
    match = _MES_RE.match(mes)
    if not match:
        raise HTTPException(status_code=400, detail=f"Mês inválido: {mes!r} (use YYYY-MM)")
    ano, mes_num = int(match.group(1)), int(match.group(2))
    if not (1 <= mes_num <= 12):
        raise HTTPException(status_code=400, detail=f"Mês fora do intervalo: {mes!r}")
    ultimo_dia = calendar.monthrange(ano, mes_num)[1]
    return date(ano, mes_num, 1), date(ano, mes_num, ultimo_dia)


def _require_token(
    x_etl_token: str = Header(default=""),
    settings: Settings = Depends(get_settings),
) -> None:
    if not settings.etl_trigger_token or x_etl_token != settings.etl_trigger_token:
        raise HTTPException(status_code=401, detail="Token inválido")


@router.post("/etl/trigger", dependencies=[Depends(_require_token)])
def trigger_etl(
    slug: str | None = None,
    slugs: str | None = None,
    incluir_privados: bool = False,
    mes: str | None = Query(default=None, description="Mês alvo da coleta no formato YYYY-MM"),
) -> dict:
    """Roda o ETL completo.

    - sem params: mês fechado mais recente, públicos.
    - ?slug=loja-fashion: roda só esse cliente.
    - ?slugs=a,b,c: lote pequeno.
    - ?incluir_privados=true: roda para todos.
    - ?mes=YYYY-MM: coleta o mês indicado (em vez do mês fechado atual).
    """
    selecionados: set[str] | None = None
    if slug:
        selecionados = {slug}
    elif slugs:
        selecionados = {s.strip() for s in slugs.split(",") if s.strip()}

    today: date | None = None
    if mes:
        inicio, _ = _mes_para_periodo(mes)
        # `periodo_referencia` devolve o mês ANTERIOR a `today`. Para coletar
        # o mês X, passamos um `today` que cai no mês seguinte.
        proximo_mes = inicio.month + 1
        ano_alvo = inicio.year + (1 if proximo_mes > 12 else 0)
        proximo_mes = 1 if proximo_mes > 12 else proximo_mes
        today = date(ano_alvo, proximo_mes, 15)

    return run_etl(
        today=today,
        slugs=selecionados,
        incluir_privados=incluir_privados,
    )


@router.post("/sync-clientes", dependencies=[Depends(_require_token)])
def trigger_sync_clientes() -> dict:
    """Sincroniza estrutura de clientes da Planilha Central (sem rodar gathers)."""
    return sync_clientes()


@router.get(
    "/periodos",
    response_model=PeriodosResponse,
    dependencies=[Depends(_require_token)],
)
def list_periodos(session: Session = Depends(get_session)) -> PeriodosResponse:
    """Lista períodos com snapshots no DB, mais recente primeiro."""
    stmt = (
        select(
            Snapshot.periodo_inicio,
            Snapshot.periodo_fim,
            func.count(func.distinct(Snapshot.cliente_id)).label("n"),
        )
        .group_by(Snapshot.periodo_inicio, Snapshot.periodo_fim)
        .order_by(Snapshot.periodo_inicio.desc())
    )
    items = [
        PeriodoDisponivel(periodo_inicio=ini, periodo_fim=fim, com_snapshot=n)
        for ini, fim, n in session.execute(stmt).all()
    ]
    return PeriodosResponse(items=items)


@router.get(
    "/clientes",
    response_model=ClientesListResponse,
    dependencies=[Depends(_require_token)],
)
def list_clientes(
    session: Session = Depends(get_session),
    mes: str | None = Query(default=None, description="Compat: equivale a de=mes&ate=mes"),
    de: str | None = Query(default=None, description="Início do range YYYY-MM"),
    ate: str | None = Query(default=None, description="Fim do range YYYY-MM"),
) -> ClientesListResponse:
    """Lista todos os clientes + snapshot mais recente dentro do range pedido.

    Precedência: de/ate > mes > sem parâmetro (snapshot mais recente de cada cliente).
    """
    # Normalizar: mes é compat layer para de=mes&ate=mes
    if de is None and ate is None and mes is not None:
        de = mes
        ate = mes

    # Se de > ate, inverter
    if de and ate and de > ate:
        de, ate = ate, de

    periodo_inicio_alvo: date | None = None
    periodo_fim_alvo: date | None = None

    if de and ate:
        de_date, _ = _mes_para_periodo(de)
        ate_date, _ = _mes_para_periodo(ate)
        periodo_inicio_alvo = de_date
        _, periodo_fim_alvo = _mes_para_periodo(ate)
        snap_filter = and_(
            Snapshot.periodo_inicio >= de_date,
            Snapshot.periodo_inicio <= ate_date,
        )
        sub = (
            select(Snapshot.cliente_id, Snapshot.id.label("snap_id"))
            .where(snap_filter)
            .distinct(Snapshot.cliente_id)
            .order_by(Snapshot.cliente_id, Snapshot.data_coleta.desc())
        ).subquery()
    else:
        sub = (
            select(Snapshot.cliente_id, Snapshot.id.label("snap_id"))
            .distinct(Snapshot.cliente_id)
            .order_by(Snapshot.cliente_id, Snapshot.periodo_fim.desc(), Snapshot.data_coleta.desc())
        ).subquery()

    stmt = (
        select(Cliente, Snapshot)
        .join(sub, sub.c.cliente_id == Cliente.id, isouter=True)
        .join(Snapshot, Snapshot.id == sub.c.snap_id, isouter=True)
        .order_by(Cliente.nome.asc())
    )

    items: list[ClienteListItem] = []
    com_snapshot = 0
    for cliente, snap in session.execute(stmt).all():
        if snap is not None:
            com_snapshot += 1
        items.append(
            ClienteListItem(
                slug=cliente.slug,
                nome=cliente.nome,
                categoria=cliente.categoria.value,
                setor=cliente.setor,
                porte=cliente.porte,
                publicar_vitrine=cliente.publicar_vitrine,
                destaque=cliente.destaque,
                periodo_inicio=snap.periodo_inicio if snap else None,
                periodo_fim=snap.periodo_fim if snap else None,
                data_coleta=snap.data_coleta if snap else None,
                faturamento=snap.faturamento if snap else None,
                investimento=snap.investimento if snap else None,
                roas=snap.roas if snap else None,
                cpa=snap.cpa if snap else None,
                leads=snap.leads if snap else None,
                vendas=snap.vendas if snap else None,
                faturamento_var_pct=snap.faturamento_var_pct if snap else None,
                roas_var_pct=snap.roas_var_pct if snap else None,
            )
        )
    return ClientesListResponse(
        items=items,
        total=len(items),
        periodo_inicio=periodo_inicio_alvo,
        periodo_fim=periodo_fim_alvo,
        com_snapshot=com_snapshot,
    )

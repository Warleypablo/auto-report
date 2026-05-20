from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_settings import Settings, get_settings
from db import get_session
from etl.collect import run_etl
from etl.sync_planilha import sync_clientes
from models import Cliente, Snapshot
from schemas import ClienteListItem, ClientesListResponse

router = APIRouter()


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
) -> dict:
    """Roda o ETL completo.

    - sem params: clientes públicos da planilha.
    - ?slug=loja-fashion: roda só esse cliente.
    - ?slugs=loja-fashion,atlas-cosmeticos: lote pequeno.
    - ?incluir_privados=true: roda para todos da planilha (público + privado).
    """
    selecionados: set[str] | None = None
    if slug:
        selecionados = {slug}
    elif slugs:
        selecionados = {s.strip() for s in slugs.split(",") if s.strip()}
    return run_etl(slugs=selecionados, incluir_privados=incluir_privados)


@router.post("/sync-clientes", dependencies=[Depends(_require_token)])
def trigger_sync_clientes() -> dict:
    """Sincroniza estrutura de clientes da Planilha Central (sem rodar gathers)."""
    return sync_clientes()


@router.get(
    "/clientes",
    response_model=ClientesListResponse,
    dependencies=[Depends(_require_token)],
)
def list_clientes(session: Session = Depends(get_session)) -> ClientesListResponse:
    """Lista todos os clientes + snapshot mais recente, sem filtrar por publicar_vitrine."""
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
    for cliente, snap in session.execute(stmt).all():
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
    return ClientesListResponse(items=items, total=len(items))

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_session
from schemas import RankingItem
from services import rankings as rankings_svc

router = APIRouter()


@router.get("/rankings/{tipo}", response_model=list[RankingItem])
def get_ranking(
    tipo: Literal["roas", "faturamento", "crescimento"],
    limit: int = Query(default=10, le=50),
    session: Session = Depends(get_session),
) -> list[RankingItem]:
    rows = rankings_svc.top_n(session, tipo, limit)
    coluna_nome = rankings_svc.COLUNA_NOME[tipo]
    return [
        RankingItem(slug=c.slug, nome=c.nome, logo_url=c.logo_url, valor=getattr(s, coluna_nome))
        for (c, s) in rows
    ]

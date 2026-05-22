from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ClienteListItem(BaseModel):
    """Item da lista interna — inclui clientes não publicados na vitrine."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    nome: str
    categoria: str
    setor: str | None
    porte: str | None
    publicar_vitrine: bool
    destaque: bool

    # Snapshot mais recente, se houver:
    periodo_inicio: date | None
    periodo_fim: date | None
    data_coleta: datetime | None
    faturamento: Decimal | None
    investimento: Decimal | None
    roas: Decimal | None
    cpa: Decimal | None
    leads: int | None
    vendas: int | None
    faturamento_var_pct: Decimal | None
    roas_var_pct: Decimal | None


class ClientesListResponse(BaseModel):
    items: list[ClienteListItem]
    total: int
    periodo_inicio: date | None = None
    periodo_fim: date | None = None
    com_snapshot: int = 0


class PeriodoDisponivel(BaseModel):
    periodo_inicio: date
    periodo_fim: date
    com_snapshot: int


class PeriodosResponse(BaseModel):
    items: list[PeriodoDisponivel]

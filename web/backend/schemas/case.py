from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class CaseListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    nome: str
    logo_url: str | None
    categoria: str
    setor: str | None
    porte: str | None
    descricao_publica: str | None
    destaque: bool
    periodo_inicio: date
    periodo_fim: date
    faturamento: Decimal | None
    investimento: Decimal | None
    roas: Decimal | None
    cpa: Decimal | None
    leads: int | None
    vendas: int | None
    faturamento_var_pct: Decimal | None
    roas_var_pct: Decimal | None


class PontoEvolucao(BaseModel):
    periodo_inicio: date
    periodo_fim: date
    faturamento: Decimal | None
    investimento: Decimal | None
    roas: Decimal | None


class CaseDetail(CaseListItem):
    metricas_detalhadas: dict[str, dict[str, Any]]
    evolucao: list[PontoEvolucao]
    data_coleta: datetime

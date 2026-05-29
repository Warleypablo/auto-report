from __future__ import annotations

import uuid

from pydantic import BaseModel


class CriativoAgregado(BaseModel):
    criativo_id: uuid.UUID
    cliente_slug: str
    cliente_nome: str
    categoria: str
    gestor_nome: str | None = None
    rede: str            # "meta" | "google"
    ad_id: str
    nome: str | None = None
    tipo: str | None = None
    preview_link: str | None = None
    thumb_url: str | None = None
    thumb_status: str
    investimento: float
    faturamento: float
    roas: float | None = None
    ctr: float | None = None
    cpa: float | None = None
    cpl: float | None = None
    impressoes: int
    clicks: int
    conversoes: float
    leads: int | None = None
    hook_rate: float | None = None
    frequency: float | None = None


class CriativosResponse(BaseModel):
    items: list[CriativoAgregado]
    total: int

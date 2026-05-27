from __future__ import annotations

import uuid
from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator


class LoginRequest(BaseModel):
    email: str
    senha: str


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nome: str
    is_admin: bool


class LoginResponse(BaseModel):
    token: str
    usuario: UsuarioResponse


class CupClienteInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str | None = None
    responsavel: str | None = None
    responsavel_geral: str | None = None
    vendedor: str | None = None
    squad: str | None = None
    segmento: str | None = None
    cluster: str | None = None
    status_conta: str | None = None
    motivo_cancelamento: str | None = None
    contrato_servico: str | None = None
    contrato_produto: str | None = None
    contrato_plano: str | None = None
    contrato_valor_recorrente: float | None = None
    contrato_status: str | None = None


class ClienteGestorItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    nome: str
    categoria: str
    gestor: str | None = None
    id_google_ads: str | None = None
    id_meta_ads: str | None = None
    id_ga4: str | None = None
    painel_url: str | None = None
    pasta_url: str | None = None
    cup_task_id: str | None = None
    ativo: bool = True
    cup: CupClienteInfo | None = None

    @field_validator("categoria", mode="before")
    @classmethod
    def coerce_categoria(cls, v: object) -> str:
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)


class ClientesGestorResponse(BaseModel):
    items: list[ClienteGestorItem]


class GestorRenameRequest(BaseModel):
    de: str
    para: str


class GestorRenameResponse(BaseModel):
    de: str
    para: str
    atualizados: int


class GestoresResponse(BaseModel):
    items: list[str]


class GestorCadastradoItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    squad: str | None


class GestorCadastradoCreate(BaseModel):
    nome: str
    squad: str | None = None


class GestorCadastradosResponse(BaseModel):
    items: list[GestorCadastradoItem]


class TriggerRequest(BaseModel):
    slug: str
    mes: str  # YYYY-MM
    frequencia: Literal["MENSAL", "SEMANAL"] = "MENSAL"


class TriggerResponse(BaseModel):
    job_id: uuid.UUID


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mes: str
    frequencia: str
    status: str
    slides_url: str | None
    erro: str | None
    created_at: datetime
    finished_at: datetime | None
    cliente_slug: str
    cliente_nome: str


class CreateUsuarioRequest(BaseModel):
    email: str
    nome: str
    senha: str
    is_admin: bool = False


class UsuarioListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    nome: str
    is_admin: bool
    ativo: bool
    n_clientes: int = 0


class UsuariosListResponse(BaseModel):
    items: list[UsuarioListItem]


class AssignClientesRequest(BaseModel):
    cliente_ids: list[uuid.UUID]


class ClienteMetricasItem(BaseModel):
    slug: str
    nome: str
    categoria: str
    periodo_inicio: str | None = None  # YYYY-MM-DD
    periodo_fim: str | None = None
    faturamento: float | None = None
    investimento: float | None = None
    roas: float | None = None
    cpa: float | None = None
    leads: int | None = None
    vendas: int | None = None
    faturamento_var_pct: float | None = None
    roas_var_pct: float | None = None


class MetricasDashboardResponse(BaseModel):
    items: list[ClienteMetricasItem]
    total_faturamento: float
    total_investimento: float
    media_roas: float | None
    total_leads: int
    total_vendas: int


class ClienteCreateRequest(BaseModel):
    nome: str
    categoria: Literal["E-commerce", "Lead Com Site", "Lead Sem Site"]
    gestor: str | None = None
    id_google_ads: str | None = None
    id_meta_ads: str | None = None
    id_ga4: str | None = None
    painel_url: str | None = None
    pasta_url: str | None = None


class ClienteEditRequest(BaseModel):
    nome: str | None = None
    categoria: Literal["E-commerce", "Lead Com Site", "Lead Sem Site"] | None = None
    gestor: str | None = None
    id_google_ads: str | None = None
    id_meta_ads: str | None = None
    id_ga4: str | None = None
    painel_url: str | None = None
    pasta_url: str | None = None


class ClienteDetalheItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    nome: str
    categoria: str
    gestor: str | None = None
    id_google_ads: str | None = None
    id_meta_ads: str | None = None
    id_ga4: str | None = None
    painel_url: str | None = None
    pasta_url: str | None = None
    ativo: bool

    @field_validator("categoria", mode="before")
    @classmethod
    def coerce_categoria(cls, v: object) -> str:
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)


# ── Inteligência ──────────────────────────────────────────────────────────

class InteligenciaAlerta(BaseModel):
    cliente_slug: str
    cliente_nome: str
    cliente_categoria: str
    severidade: str
    sinais: list[dict]
    narrativa: str | None = None


class InteligenciaResponse(BaseModel):
    mes: str
    alertas: list[InteligenciaAlerta]


class InteligenciaGenerateResponse(BaseModel):
    mes: str
    gerados: int
    sem_sinais: int
    sem_dados: int
    erros: int

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class ClienteGestorItem(BaseModel):
    id: uuid.UUID
    slug: str
    nome: str
    categoria: str


class ClientesGestorResponse(BaseModel):
    items: list[ClienteGestorItem]


class TriggerRequest(BaseModel):
    slug: str
    mes: str  # YYYY-MM


class TriggerResponse(BaseModel):
    job_id: uuid.UUID


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    mes: str
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

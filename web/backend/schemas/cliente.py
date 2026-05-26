from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from models.cliente import Categoria


class ClienteLoginRequest(BaseModel):
    cnpj: str = Field(..., min_length=11, max_length=20, description="CNPJ formatado ou só dígitos")


class ClientePublic(BaseModel):
    id: uuid.UUID
    slug: str
    nome: str
    categoria: Categoria
    logo_url: str | None = None
    setor: str | None = None


class ClienteLoginResponse(BaseModel):
    token: str
    cliente: ClientePublic

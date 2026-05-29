from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Categoria(str, enum.Enum):
    ECOMMERCE = "E-commerce"
    LEAD_COM_SITE = "Lead Com Site"
    LEAD_SEM_SITE = "Lead Sem Site"


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    categoria: Mapped[Categoria] = mapped_column(Enum(Categoria, name="categoria"), nullable=False)
    gestor: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    gestor_travado: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    id_google_ads: Mapped[str | None] = mapped_column(String, nullable=True)
    id_meta_ads: Mapped[str | None] = mapped_column(String, nullable=True)
    id_ga4: Mapped[str | None] = mapped_column(String, nullable=True)
    painel_url: Mapped[str | None] = mapped_column(String, nullable=True)
    pasta_url: Mapped[str | None] = mapped_column(String, nullable=True)
    cup_task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    setor: Mapped[str | None] = mapped_column(String, nullable=True)
    porte: Mapped[str | None] = mapped_column(String, nullable=True)
    descricao_publica: Mapped[str | None] = mapped_column(String, nullable=True)
    publicar_vitrine: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    destaque: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list["Snapshot"]] = relationship(
        "Snapshot", back_populates="cliente", cascade="all, delete-orphan"
    )

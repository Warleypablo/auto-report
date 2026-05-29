from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class RedeAnuncio(str, enum.Enum):
    META = "META"
    GOOGLE = "GOOGLE"


class ThumbStatus(str, enum.Enum):
    PENDENTE = "pendente"
    OK = "ok"
    SEM_IMAGEM = "sem_imagem"
    ERRO = "erro"


class Criativo(Base):
    __tablename__ = "criativos"
    __table_args__ = (
        UniqueConstraint("cliente_id", "rede", "ad_id", name="uq_criativo_cliente_rede_ad"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rede: Mapped[RedeAnuncio] = mapped_column(Enum(RedeAnuncio, name="rede_anuncio"), nullable=False)
    ad_id: Mapped[str] = mapped_column(String, nullable=False)
    nome: Mapped[str | None] = mapped_column(String, nullable=True)
    tipo: Mapped[str | None] = mapped_column(String, nullable=True)
    preview_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumb_status: Mapped[ThumbStatus] = mapped_column(
        Enum(ThumbStatus, name="thumb_status"), nullable=False, default=ThumbStatus.PENDENTE
    )
    primeiro_dia: Mapped[date | None] = mapped_column(Date, nullable=True)
    ultimo_dia: Mapped[date | None] = mapped_column(Date, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    thumb: Mapped["CriativoThumb | None"] = relationship(
        "CriativoThumb", back_populates="criativo", cascade="all, delete-orphan", uselist=False
    )


class CriativoThumb(Base):
    __tablename__ = "criativo_thumbs"

    criativo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("criativos.id", ondelete="CASCADE"), primary_key=True
    )
    conteudo: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    mime: Mapped[str] = mapped_column(String, nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    criativo: Mapped["Criativo"] = relationship("Criativo", back_populates="thumb")

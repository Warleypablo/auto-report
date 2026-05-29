from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .criativo import RedeAnuncio  # reusa o MESMO Enum (não redefinir)


class AdInsight(Base):
    __tablename__ = "ad_insights"
    __table_args__ = (
        UniqueConstraint(
            "cliente_id", "rede", "ad_id", "dia", name="uq_ad_insight_cliente_rede_ad_dia"
        ),
        Index("ix_ad_insights_cliente_dia", "cliente_id", "dia"),
        Index("ix_ad_insights_cliente_rede_dia", "cliente_id", "rede", "dia"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rede: Mapped[RedeAnuncio] = mapped_column(Enum(RedeAnuncio, name="rede_anuncio"), nullable=False)
    ad_id: Mapped[str] = mapped_column(String, nullable=False)
    dia: Mapped[date] = mapped_column(Date, nullable=False)

    investimento: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    faturamento: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False, default=0)
    conversoes: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    leads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressoes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    video_3s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

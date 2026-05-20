from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Frequencia(str, enum.Enum):
    SEMANAL = "SEMANAL"
    MENSAL = "MENSAL"


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (
        UniqueConstraint("cliente_id", "periodo_inicio", "periodo_fim", name="uq_snapshot_periodo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fim: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    frequencia: Mapped[Frequencia] = mapped_column(Enum(Frequencia, name="frequencia"), nullable=False)
    data_coleta: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    faturamento: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    investimento: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    roas: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    cpa: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    leads: Mapped[int | None] = mapped_column(nullable=True)
    vendas: Mapped[int | None] = mapped_column(nullable=True)

    faturamento_var_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    roas_var_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    metricas_detalhadas: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_dados: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="snapshots")

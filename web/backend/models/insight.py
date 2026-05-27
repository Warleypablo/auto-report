from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Insight(Base):
    __tablename__ = "insights"
    __table_args__ = (
        UniqueConstraint("cliente_id", "mes", name="uq_insight_cliente_mes"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mes: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    sinais: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    narrativa: Mapped[str | None] = mapped_column(Text, nullable=True)
    gerado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cliente: Mapped["Cliente"] = relationship("Cliente", viewonly=True)

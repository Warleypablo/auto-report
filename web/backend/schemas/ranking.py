from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RankingItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    nome: str
    logo_url: str | None
    valor: Decimal

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from models import AdInsight, Categoria, Cliente, Criativo, RedeAnuncio, ThumbStatus
from models.base import Base

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture(scope="module")
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def cliente_id(TS):
    slug = f"test-criativos-{uuid.uuid4().hex[:8]}"
    with TS() as s:
        c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE, ativo=True)
        s.add(c)
        s.commit()
        cid = c.id
    yield cid
    with TS() as s:
        c = s.get(Cliente, cid)
        if c:
            s.delete(c)
            s.commit()


def test_upsert_ad_insight_insere_e_atualiza_sem_duplicar(TS, cliente_id):
    from etl.collect_criativos import upsert_ad_insight

    campos = dict(
        cliente_id=cliente_id,
        rede=RedeAnuncio.META,
        ad_id="ad-1",
        dia=date(2026, 5, 1),
        investimento=Decimal("10.00"),
        faturamento=Decimal("40.00"),
        conversoes=Decimal("2"),
        leads=None,
        impressoes=1000,
        clicks=10,
        video_3s=300,
        reach=800,
    )

    with TS() as s:
        upsert_ad_insight(s, **campos)
        s.commit()

    # mesmo (cliente, rede, ad_id, dia) com novos valores → UPDATE, não duplica
    campos2 = {**campos, "investimento": Decimal("99.00"), "faturamento": Decimal("123.00")}
    with TS() as s:
        upsert_ad_insight(s, **campos2)
        s.commit()

    with TS() as s:
        rows = s.scalars(
            select(AdInsight).where(
                AdInsight.cliente_id == cliente_id,
                AdInsight.ad_id == "ad-1",
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].investimento == Decimal("99.00")
        assert rows[0].faturamento == Decimal("123.00")
        assert rows[0].dia == date(2026, 5, 1)

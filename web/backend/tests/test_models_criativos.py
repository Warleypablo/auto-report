import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models import (
    AdInsight,
    Categoria,
    Cliente,
    Criativo,
    CriativoThumb,
    RedeAnuncio,
    ThumbStatus,
)
from models.base import Base

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _cliente(s, slug="c-criativos"):
    c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


def test_cliente_gestor_travado_default_false(TS):
    with TS() as s:
        c = _cliente(s)
        assert c.gestor_travado is False

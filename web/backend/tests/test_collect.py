import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from db import SessionLocal
from etl.cliente_publico import ClientePublico
from etl.collect import processar_cliente
from models import Categoria, Cliente, Snapshot
from models.snapshot import Frequencia


class FakeCoreCliente:
    def __init__(self, nome, categoria):
        self.nome = nome
        self.categoria = categoria
        self.extras = {}


@pytest.fixture
def cliente_id():
    slug = f"test-collect-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as s:
        c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE, publicar_vitrine=True)
        s.add(c)
        s.commit()
        cid = c.id
    yield cid
    with SessionLocal() as s:
        c = s.get(Cliente, cid)
        if c:
            s.delete(c)
            s.commit()


def test_processar_cliente_grava_snapshot(cliente_id):
    pub = ClientePublico(
        nome="Acme",
        slug="acme",
        categoria="E-commerce",
        publicar_vitrine=True,
        logo_url=None,
        descricao_publica=None,
        setor=None,
        porte=None,
        cliente_core=FakeCoreCliente("Acme", "E-commerce"),
    )

    fake_handler = MagicMock()
    fake_handler.coletar_dados.return_value = {
        "{{fat_sem}}": "R$ 1.000,00",
        "{{roas}}": "4,2x",
    }

    with patch("etl.collect._get_handler", return_value=fake_handler):
        ok = processar_cliente(
            pub=pub,
            cliente_db_id=cliente_id,
            periodo_ref=MagicMock(inicio=date(2026, 1, 1), fim=date(2026, 1, 31)),
            periodo_comp=MagicMock(),
            frequencia=Frequencia.MENSAL,
        )

    assert ok is True
    with SessionLocal() as s:
        snap = s.scalar(select(Snapshot).where(Snapshot.cliente_id == cliente_id))
        assert snap is not None
        assert snap.faturamento == Decimal("1000")
        assert snap.roas == Decimal("4.2")


def test_processar_cliente_falha_handler_retorna_false(cliente_id):
    pub = ClientePublico(
        nome="Acme",
        slug="acme",
        categoria="E-commerce",
        publicar_vitrine=True,
        logo_url=None,
        descricao_publica=None,
        setor=None,
        porte=None,
        cliente_core=FakeCoreCliente("Acme", "E-commerce"),
    )

    fake_handler = MagicMock()
    fake_handler.coletar_dados.side_effect = RuntimeError("API caiu")

    with patch("etl.collect._get_handler", return_value=fake_handler):
        ok = processar_cliente(
            pub=pub,
            cliente_db_id=cliente_id,
            periodo_ref=MagicMock(inicio=date(2026, 2, 1), fim=date(2026, 2, 28)),
            periodo_comp=MagicMock(),
            frequencia=Frequencia.MENSAL,
        )

    assert ok is False

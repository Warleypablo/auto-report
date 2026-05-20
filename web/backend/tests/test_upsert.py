import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from db import SessionLocal
from etl.upsert import upsert_snapshot
from models import Categoria, Cliente, Snapshot
from models.snapshot import Frequencia


@pytest.fixture
def cliente_id():
    """Cria cliente fresco no DB com slug único, retorna o id e limpa depois."""
    slug = f"test-upsert-{uuid.uuid4().hex[:8]}"
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


def test_insere_novo(cliente_id):
    with SessionLocal() as s:
        upsert_snapshot(
            s,
            cliente_id=cliente_id,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 1, 31),
            frequencia=Frequencia.MENSAL,
            dados={"faturamento": Decimal("100"), "metricas_detalhadas": {}, "raw_dados": {}},
        )
        s.commit()
        n = s.scalar(select(Snapshot).where(Snapshot.cliente_id == cliente_id))
        assert n.faturamento == Decimal("100")


def test_atualiza_mesmo_periodo(cliente_id):
    base = dict(
        cliente_id=cliente_id,
        periodo_inicio=date(2026, 1, 1),
        periodo_fim=date(2026, 1, 31),
        frequencia=Frequencia.MENSAL,
    )
    with SessionLocal() as s:
        upsert_snapshot(
            s, **base,
            dados={"faturamento": Decimal("100"), "metricas_detalhadas": {}, "raw_dados": {}},
        )
        s.commit()
        upsert_snapshot(
            s, **base,
            dados={"faturamento": Decimal("200"), "metricas_detalhadas": {}, "raw_dados": {}},
        )
        s.commit()

        snaps = s.scalars(select(Snapshot).where(Snapshot.cliente_id == cliente_id)).all()
        assert len(snaps) == 1
        assert snaps[0].faturamento == Decimal("200")

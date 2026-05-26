from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app_settings import Settings, get_settings
from db import get_session
from models import Cliente
from models.base import Base
from models.cliente import Categoria
from models.snapshot import Frequencia, Snapshot


TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def app_with_db():
    engine = create_engine(TEST_DB_URL)

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS staging.cup_clientes (
                task_id text PRIMARY KEY, nome text, cnpj text
            )
        """))
        conn.execute(text("DELETE FROM staging.cup_clientes"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine)

    from api.cliente import router

    app = FastAPI()
    app.include_router(router, prefix="/cliente")

    def s_dep():
        with TS() as s:
            yield s

    def cfg_dep():
        return Settings(database_url=TEST_DB_URL)

    app.dependency_overrides[get_session] = s_dep
    app.dependency_overrides[get_settings] = cfg_dep
    return app, TS


def _seed_cliente_with_snaps(TS, *, nome, cnpj, task_id, snaps=None):
    snaps = snaps if snaps is not None else [("2026-04", 1000, 100), ("2026-03", 800, 80)]
    with TS() as s:
        c = Cliente(
            slug=nome.lower(),
            nome=nome,
            categoria=Categoria.LEAD_COM_SITE,
            cup_task_id=task_id,
            ativo=True,
        )
        s.add(c)
        s.commit()
        s.refresh(c)
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome, cnpj) VALUES (:t, :n, :c)"),
            {"t": task_id, "n": nome, "c": cnpj},
        )
        for mes, fat, inv in snaps:
            ano, m = int(mes[:4]), int(mes[5:7])
            s.add(Snapshot(
                cliente_id=c.id,
                periodo_inicio=date(ano, m, 1),
                periodo_fim=date(ano, m, 28),
                frequencia=Frequencia.MENSAL,
                faturamento=Decimal(fat),
                investimento=Decimal(inv),
                roas=Decimal("3.5"),
                cpa=Decimal(50),
                leads=20,
                vendas=5,
            ))
        s.commit()
        return c.id


def _login(client, cnpj):
    return client.post("/cliente/auth/login", json={"cnpj": cnpj}).json()["token"]


def test_timeline_returns_own_snapshots(app_with_db):
    app, TS = app_with_db
    _seed_cliente_with_snaps(TS, nome="A", cnpj="55555555000155", task_id="tA")
    client = TestClient(app)
    tok = _login(client, "55555555000155")

    r = client.get("/cliente/metricas/timeline?meses=12",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["items"]) == 2
    assert data["items"][0]["mes"] == "2026-03"
    assert data["items"][1]["mes"] == "2026-04"
    assert "gestor" not in data
    assert "slides_url" not in str(data)


def test_timeline_isolation(app_with_db):
    """Cliente A logado não vê snapshots de B."""
    app, TS = app_with_db
    _seed_cliente_with_snaps(TS, nome="A", cnpj="66666666000166", task_id="tA",
                             snaps=[("2026-04", 1000, 100)])
    _seed_cliente_with_snaps(TS, nome="B", cnpj="77777777000177", task_id="tB",
                             snaps=[("2026-04", 9999, 999)])
    client = TestClient(app)
    tok_a = _login(client, "66666666000166")

    r = client.get("/cliente/metricas/timeline?meses=12",
                   headers={"Authorization": f"Bearer {tok_a}"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["faturamento"] == 1000.0


def test_timeline_empty(app_with_db):
    app, TS = app_with_db
    _seed_cliente_with_snaps(TS, nome="C", cnpj="88888888000188", task_id="tC", snaps=[])
    client = TestClient(app)
    tok = _login(client, "88888888000188")

    r = client.get("/cliente/metricas/timeline?meses=12",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json() == {"items": []}


def test_breakdown_isolation(app_with_db):
    app, TS = app_with_db
    with TS() as s:
        c_a = Cliente(slug="a-brk", nome="A", categoria=Categoria.LEAD_COM_SITE,
                      cup_task_id="tAb", ativo=True)
        s.add(c_a)
        s.commit()
        s.refresh(c_a)
        s.execute(text(
            "INSERT INTO staging.cup_clientes (task_id, nome, cnpj) "
            "VALUES ('tAb', 'A', '99999999000199')"
        ))
        s.commit()
        s.add(Snapshot(
            cliente_id=c_a.id,
            periodo_inicio=date(2026, 4, 1),
            periodo_fim=date(2026, 4, 30),
            frequencia=Frequencia.MENSAL,
            raw_dados={
                "{{nome_adf1}}": "Ad do A",
                "{{inv_adf1}}": "R$ 100,00",
            },
        ))
        s.commit()

    client = TestClient(app)
    tok = _login(client, "99999999000199")
    r = client.get("/cliente/metricas/breakdown?mes=2026-04",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["meta_ads"]) == 1
    assert data["meta_ads"][0]["nome"] == "Ad do A"
    assert data["meta_ads"][0]["investimento"] == 100.0
    assert data["google_ads"] == []


def test_meses_disponiveis(app_with_db):
    app, TS = app_with_db
    _seed_cliente_with_snaps(TS, nome="M", cnpj="10101010000110", task_id="tM",
                             snaps=[("2026-04", 1000, 100), ("2026-03", 900, 90)])
    client = TestClient(app)
    tok = _login(client, "10101010000110")

    r = client.get("/cliente/metricas/meses-disponiveis",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json() == {"meses": ["2026-04", "2026-03"]}

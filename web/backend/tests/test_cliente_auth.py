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


TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def app_with_db():
    engine = create_engine(TEST_DB_URL)

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS staging.cup_clientes (
                task_id text PRIMARY KEY,
                nome text,
                cnpj text
            )
        """))
        conn.execute(text("DELETE FROM staging.cup_clientes"))

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    TestSession = sessionmaker(bind=engine)

    from api.cliente import router as cliente_router

    app = FastAPI()
    app.include_router(cliente_router, prefix="/cliente")

    def override_session():
        with TestSession() as s:
            yield s

    def override_settings():
        return Settings(database_url=TEST_DB_URL)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings

    return app, TestSession


def _seed_cliente(TestSession, *, nome, cnpj, task_id="task-1", ativo=True):
    with TestSession() as s:
        c = Cliente(
            slug=nome.lower().replace(" ", "-"),
            nome=nome,
            categoria=Categoria.LEAD_COM_SITE,
            cup_task_id=task_id,
            ativo=ativo,
        )
        s.add(c)
        s.commit()
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome, cnpj) VALUES (:t, :n, :c)"),
            {"t": task_id, "n": nome, "c": cnpj},
        )
        s.commit()
        return c.id


def test_login_with_formatted_cnpj_returns_token(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente(TS, nome="Cliente A", cnpj="12345678000190")

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "12.345.678/0001-90"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data
    assert data["cliente"]["id"] == str(cid)
    assert data["cliente"]["nome"] == "Cliente A"
    assert "gestor" not in data["cliente"]
    assert "cup_task_id" not in data["cliente"]


def test_login_with_digits_only(app_with_db):
    app, TS = app_with_db
    _seed_cliente(TS, nome="Cliente A", cnpj="12345678000190")

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "12345678000190"})
    assert r.status_code == 200


def test_login_cnpj_not_found(app_with_db):
    app, TS = app_with_db
    _seed_cliente(TS, nome="Cliente A", cnpj="12345678000190")

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "99999999999999"})
    assert r.status_code == 401
    assert "não encontrado" in r.json()["detail"].lower()


def test_login_inactive_cliente(app_with_db):
    app, TS = app_with_db
    _seed_cliente(TS, nome="Inativa", cnpj="11111111000111", ativo=False)

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "11111111000111"})
    assert r.status_code == 401
    assert "inativa" in r.json()["detail"].lower()


def test_login_multiple_cnpjs(app_with_db):
    app, TS = app_with_db
    _seed_cliente(TS, nome="A", cnpj="22222222000122", task_id="t1")
    _seed_cliente(TS, nome="B", cnpj="22222222000122", task_id="t2")

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "22222222000122"})
    assert r.status_code == 401
    detail = r.json()["detail"].lower()
    assert "múltiplas" in detail or "multiplas" in detail


def test_login_broken_link(app_with_db):
    """CNPJ existe em cup_clientes mas não há cliente correspondente."""
    app, TS = app_with_db
    with TS() as s:
        s.execute(text(
            "INSERT INTO staging.cup_clientes (task_id, nome, cnpj) "
            "VALUES ('orfao', 'X', '33333333000133')"
        ))
        s.commit()

    client = TestClient(app)
    r = client.post("/cliente/auth/login", json={"cnpj": "33333333000133"})
    assert r.status_code == 401


def test_logout_returns_204(app_with_db):
    """Logout é stateless: backend só sinaliza ok; frontend limpa cookie."""
    app, TS = app_with_db
    _seed_cliente(TS, nome="Cliente Y", cnpj="44444444000144")

    client = TestClient(app)
    login = client.post("/cliente/auth/login", json={"cnpj": "44444444000144"})
    token = login.json()["token"]

    r = client.post("/cliente/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 204


def test_cliente_deactivated_after_token_emission(app_with_db):
    """Token foi emitido com cliente ativo; cliente vira ativo=False; chamadas
    a rotas protegidas passam a falhar com 401 (require_cliente revalida no DB)."""
    app, TS = app_with_db
    cid = _seed_cliente(TS, nome="Será desativada", cnpj="55555555000155")

    client = TestClient(app)
    login = client.post("/cliente/auth/login", json={"cnpj": "55555555000155"})
    assert login.status_code == 200
    token = login.json()["token"]

    # Acesso normal funciona
    r_ok = client.get("/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert r_ok.status_code == 200

    # Desativa o cliente diretamente no DB
    with TS() as s:
        from sqlalchemy import update
        from models import Cliente

        s.execute(update(Cliente).where(Cliente.id == cid).values(ativo=False))
        s.commit()

    r_after = client.get("/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert r_after.status_code == 401

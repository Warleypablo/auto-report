"""Testa que gestores só vêem os próprios clientes e admins vêem todos."""
from __future__ import annotations

import unicodedata
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app_settings import Settings
from db import get_session
from models import Cliente, Usuario, UsuarioCliente
from models.base import Base
from models.cliente import Categoria
from api.auth import hash_password, require_auth, require_admin


TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def app_with_db():
    engine = create_engine(TEST_DB_URL)

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
        conn.execute(text("DROP TABLE IF EXISTS staging.cup_contratos"))
        conn.execute(text("DROP TABLE IF EXISTS staging.cup_clientes"))
        conn.execute(text("""
            CREATE TABLE staging.cup_clientes (
                task_id text PRIMARY KEY,
                nome text,
                cnpj text,
                subtask_ids text,
                responsavel text,
                responsavel_geral text,
                vendedor text,
                squad text,
                segmento text,
                cluster text,
                status text,
                status_conta text,
                motivo_cancelamento text
            )
        """))
        conn.execute(text("""
            CREATE TABLE staging.cup_contratos (
                id_subtask text,
                id_task text,
                servico text,
                produto text,
                plano text,
                valorr numeric,
                status text,
                responsavel text,
                data_inicio date
            )
        """))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine)

    from api.gestor import router

    app = FastAPI()
    app.include_router(router, prefix="/gestor")

    def s_dep():
        with TS() as s:
            yield s

    def cfg_dep():
        return Settings(database_url=TEST_DB_URL)

    app.dependency_overrides[get_session] = s_dep
    app.dependency_overrides[Settings] = cfg_dep

    yield app, TS

    app.dependency_overrides.clear()


def _create_user(TS, *, is_admin: bool = False) -> uuid.UUID:
    with TS() as s:
        u = Usuario(
            email=f"test-{uuid.uuid4().hex[:8]}@test.com",
            nome="Test",
            senha_hash=hash_password("x"),
            is_admin=is_admin,
            ativo=True,
        )
        s.add(u)
        s.commit()
        s.refresh(u)
        return u.id


def _create_cliente(TS, nome: str) -> uuid.UUID:
    with TS() as s:
        c = Cliente(
            slug=f"slug-{uuid.uuid4().hex[:8]}",
            nome=nome,
            categoria=Categoria.ECOMMERCE,
            ativo=True,
        )
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


def _link(TS, usuario_id: uuid.UUID, cliente_id: uuid.UUID) -> None:
    with TS() as s:
        s.add(UsuarioCliente(usuario_id=usuario_id, cliente_id=cliente_id))
        s.commit()


def _make_auth_override(TS, user_id: uuid.UUID):
    """Returns a FastAPI dependency that returns the user from DB (no token needed)."""
    def fake_auth():
        with TS() as s:
            return s.get(Usuario, user_id)
    return fake_auth


def test_gestor_ve_somente_proprios_clientes(app_with_db):
    app, TS = app_with_db

    gestor_a_id = _create_user(TS)
    gestor_b_id = _create_user(TS)
    c_a_id = _create_cliente(TS, "Cliente A")
    c_b_id = _create_cliente(TS, "Cliente B")
    _link(TS, gestor_a_id, c_a_id)
    _link(TS, gestor_b_id, c_b_id)

    app.dependency_overrides[require_auth] = _make_auth_override(TS, gestor_a_id)
    app.dependency_overrides[require_admin] = _make_auth_override(TS, gestor_a_id)

    client = TestClient(app)
    resp = client.get("/gestor/clientes")
    assert resp.status_code == 200
    nomes = [i["nome"] for i in resp.json()["items"]]
    assert "Cliente A" in nomes
    assert "Cliente B" not in nomes


def test_admin_ve_todos_clientes(app_with_db):
    app, TS = app_with_db

    admin_id = _create_user(TS, is_admin=True)
    gestor_id = _create_user(TS)
    c1_id = _create_cliente(TS, "Exclusivo Gestor")
    _link(TS, gestor_id, c1_id)

    app.dependency_overrides[require_auth] = _make_auth_override(TS, admin_id)
    app.dependency_overrides[require_admin] = _make_auth_override(TS, admin_id)

    client = TestClient(app)
    resp = client.get("/gestor/clientes")
    assert resp.status_code == 200
    nomes = [i["nome"] for i in resp.json()["items"]]
    assert "Exclusivo Gestor" in nomes


def test_gestor_sem_clientes_ve_lista_vazia(app_with_db):
    app, TS = app_with_db

    gestor_id = _create_user(TS)

    app.dependency_overrides[require_auth] = _make_auth_override(TS, gestor_id)
    app.dependency_overrides[require_admin] = _make_auth_override(TS, gestor_id)

    client = TestClient(app)
    resp = client.get("/gestor/clientes")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_seed_email_derivation():
    _CONECTIVAS = {"da", "de", "do", "das", "dos", "e", "von", "van", "del"}

    def _remover_acentos(s: str) -> str:
        return "".join(
            c for c in unicodedata.normalize("NFD", s)
            if unicodedata.category(c) != "Mn"
        )

    def _derivar_email(nome: str) -> str:
        tokens = [t for t in nome.split() if t.lower() not in _CONECTIVAS]
        primeiro = _remover_acentos(tokens[0]).lower()
        ultimo = _remover_acentos(tokens[-1]).lower() if len(tokens) > 1 else primeiro
        return f"{primeiro}.{ultimo}@turbopartners.com.br"

    assert _derivar_email("José Neto") == "jose.neto@turbopartners.com.br"
    assert _derivar_email("Bruno da Silva") == "bruno.silva@turbopartners.com.br"
    assert _derivar_email("Gabriel Taufner") == "gabriel.taufner@turbopartners.com.br"
    assert _derivar_email("Gustavo S Pires") == "gustavo.pires@turbopartners.com.br"
    assert _derivar_email("Victor Matsushita") == "victor.matsushita@turbopartners.com.br"

import uuid
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app_settings import Settings, get_settings
from db import get_session
from models import Cliente, Usuario
from models.base import Base
from models.cliente import Categoria


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
                subtask_ids text
            )
        """))
        conn.execute(text("""
            CREATE TABLE staging.cup_contratos (
                id_subtask text,
                id_task text,
                servico text,
                status text,
                responsavel text,
                data_inicio date
            )
        """))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine)

    from api.gestor import router
    from api.auth import require_auth, require_admin

    app = FastAPI()
    app.include_router(router, prefix="/gestor")

    def s_dep():
        with TS() as s:
            yield s

    def cfg_dep():
        return Settings(database_url=TEST_DB_URL)

    admin = Usuario(
        email="admin@test.com", nome="Admin",
        senha_hash="x", is_admin=True, ativo=True,
    )
    with TS() as s:
        s.add(admin)
        s.commit()
        s.refresh(admin)
        admin_id = admin.id

    def fake_admin():
        with TS() as s:
            return s.get(Usuario, admin_id)

    app.dependency_overrides[get_session] = s_dep
    app.dependency_overrides[get_settings] = cfg_dep
    app.dependency_overrides[require_auth] = fake_admin
    app.dependency_overrides[require_admin] = fake_admin
    return app, TS


def _seed_cliente(TS, *, nome, gestor, task_id, subtask_id, gestor_travado=False):
    with TS() as s:
        c = Cliente(
            slug=nome.lower().replace(" ", "-"),
            nome=nome,
            categoria=Categoria.ECOMMERCE,
            gestor=gestor,
            cup_task_id=task_id,
            ativo=True,
            gestor_travado=gestor_travado,
        )
        s.add(c)
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome, subtask_ids) "
                 "VALUES (:t, :n, :s)"),
            {"t": task_id, "n": nome, "s": subtask_id},
        )
        s.execute(
            text("INSERT INTO staging.cup_contratos "
                 "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                 "VALUES (:sub, :task, 'Gestão de Performance', 'ativo', :resp, :dt)"),
            {"sub": subtask_id, "task": task_id, "resp": "Novo Gestor",
             "dt": date(2026, 1, 1)},
        )
        s.commit()
        s.refresh(c)
        return c.id


def test_patch_seta_gestor_travado(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente(TS, nome="Loja A", gestor="Velho Gestor",
                        task_id="t1", subtask_id="s1")
    client = TestClient(app)

    r = client.patch(f"/gestor/clientes/{cid}", json={"gestor_travado": True})
    assert r.status_code == 200, r.text
    assert r.json()["gestor_travado"] is True

    with TS() as s:
        assert s.get(Cliente, cid).gestor_travado is True


def test_sync_sobrescreve_gestor_alterado(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente(TS, nome="Loja B", gestor="Velho Gestor",
                        task_id="t2", subtask_id="s2")
    client = TestClient(app)

    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["atualizados"] == 1

    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Novo Gestor"


def test_sync_respeita_gestor_travado(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente(TS, nome="Loja C", gestor="Velho Gestor",
                        task_id="t3", subtask_id="s3", gestor_travado=True)
    client = TestClient(app)

    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["atualizados"] == 0
    assert body["a_atualizar"] == 0

    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Velho Gestor"


def test_sync_idempotente(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente(TS, nome="Loja D", gestor="Velho Gestor",
                        task_id="t4", subtask_id="s4")
    client = TestClient(app)

    r1 = client.post("/gestor/clientes/sync-gestores")
    assert r1.status_code == 200, r1.text
    assert r1.json()["atualizados"] == 1

    r2 = client.post("/gestor/clientes/sync-gestores")
    assert r2.status_code == 200, r2.text
    assert r2.json()["atualizados"] == 0
    assert r2.json()["a_atualizar"] == 0

    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Novo Gestor"


def _seed_cliente_resp(TS, *, nome, gestor, task_id, resp, status="ativo",
                       data_inicio=date(2026, 1, 1), cup_task_id=None):
    """Cliente + contrato com responsável/serviço/status custom. cup_task_id
    default = task_id; passe '' para simular cliente sem vínculo."""
    link = task_id if cup_task_id is None else (cup_task_id or None)
    with TS() as s:
        c = Cliente(
            slug=nome.lower().replace(" ", "-"), nome=nome,
            categoria=Categoria.ECOMMERCE, gestor=gestor,
            cup_task_id=link, ativo=True,
        )
        s.add(c)
        s.execute(
            text("INSERT INTO staging.cup_contratos "
                 "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                 "VALUES (:sub, :task, 'Gestão de Performance', :st, :resp, :dt)"),
            {"sub": task_id + "-s", "task": task_id, "st": status,
             "resp": resp, "dt": data_inicio},
        )
        s.commit()
        s.refresh(c)
        return c.id


def test_sync_normaliza_capitalizacao_do_responsavel(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_resp(TS, nome="Loja N", gestor="Rayan Coutinho",
                             task_id="tn", resp="rayan coutinho")
    client = TestClient(app)
    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Rayan Coutinho"


def test_sync_ignora_cliente_sem_vinculo(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_resp(TS, nome="Loja SV", gestor="Velho",
                             task_id="tsv", resp="Novo Gestor", cup_task_id="")
    client = TestClient(app)
    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    assert r.json()["atualizados"] == 0
    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Velho"


def test_sync_prefere_contrato_ativo(app_with_db):
    app, TS = app_with_db
    with TS() as s:
        c = Cliente(slug="loja-ac", nome="Loja AC", categoria=Categoria.ECOMMERCE,
                    gestor="Velho", cup_task_id="tac", ativo=True)
        s.add(c)
        for sub, st, resp, dt in [
            ("tac-1", "cancelado/inativo", "Antigo", date(2026, 5, 1)),
            ("tac-2", "ativo", "Atual", date(2026, 1, 1)),
        ]:
            s.execute(
                text("INSERT INTO staging.cup_contratos "
                     "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                     "VALUES (:sub, 'tac', 'Gestão de Performance', :st, :resp, :dt)"),
                {"sub": sub, "st": st, "resp": resp, "dt": dt},
            )
        s.commit(); s.refresh(c); cid = c.id
    client = TestClient(app)
    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Atual"


def test_sync_conta_contrato_sem_responsavel(app_with_db):
    app, TS = app_with_db
    with TS() as s:
        c = Cliente(slug="loja-sr", nome="Loja SR", categoria=Categoria.ECOMMERCE,
                    gestor="Velho", cup_task_id="tsr", ativo=True)
        s.add(c)
        s.execute(
            text("INSERT INTO staging.cup_contratos "
                 "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                 "VALUES ('tsr-1', 'tsr', 'Gestão de Performance', 'ativo', '   ', :dt)"),
            {"dt": date(2026, 1, 1)},
        )
        s.commit(); s.refresh(c); cid = c.id
    client = TestClient(app)
    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["com_contrato_performance"] >= 1
    assert body["com_responsavel"] == 0
    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Velho"


def _seed_cup_cliente(TS, task_id, nome):
    with TS() as s:
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome) VALUES (:t, :n)"),
            {"t": task_id, "n": nome},
        )
        s.commit()

def _seed_cliente_sem_cup(TS, nome):
    with TS() as s:
        c = Cliente(slug=nome.lower().replace(" ", "-"), nome=nome,
                    categoria=Categoria.ECOMMERCE, ativo=True, cup_task_id=None)
        s.add(c); s.commit(); s.refresh(c)
        return str(c.id)


def test_automatch_auto_aplica_match_forte(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_sem_cup(TS, "Noway Drinks")
    _seed_cup_cliente(TS, "cup-noway", "Noway Drink")
    _seed_cup_cliente(TS, "cup-outro", "Padaria do Zé")
    client = TestClient(app)

    prev = client.post("/gestor/clickup/automatch?dry_run=true")
    assert prev.status_code == 200, prev.text
    body = prev.json()
    noway = next(m for m in body["matches"] if m["cliente_nome"] == "Noway Drinks")
    assert noway["task_id"] == "cup-noway"
    assert noway["score"] >= 0.90

    apply = client.post("/gestor/clickup/automatch?dry_run=false")
    assert apply.status_code == 200, apply.text
    assert apply.json()["aplicados"] >= 1
    with TS() as s:
        assert s.get(Cliente, uuid.UUID(cid)).cup_task_id == "cup-noway"


def test_automatch_nao_aplica_lixo(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_sem_cup(TS, "Nomã")
    _seed_cup_cliente(TS, "cup-bueno", "Bueno Mate")
    client = TestClient(app)
    body = client.post("/gestor/clickup/automatch?dry_run=false").json()
    assert all(m["cliente_nome"] != "Nomã" for m in body["matches"])
    with TS() as s:
        assert s.get(Cliente, uuid.UUID(cid)).cup_task_id is None


def test_sync_tudo_vincula_e_preenche_gestor(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_sem_cup(TS, "Zacca")
    _seed_cup_cliente(TS, "cup-zacca", "Zacca Brasil")
    with TS() as s:
        s.execute(
            text("INSERT INTO staging.cup_contratos "
                 "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                 "VALUES ('z-1', 'cup-zacca', 'Gestão de Performance', 'ativo', "
                 "'thiago m.', :dt)"),
            {"dt": date(2026, 1, 1)},
        )
        s.commit()
    client = TestClient(app)

    r = client.post("/gestor/clickup/sync-tudo")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vinculos_aplicados"] >= 1
    assert body["gestores_atualizados"] >= 1
    with TS() as s:
        c = s.get(Cliente, uuid.UUID(cid))
        assert c.cup_task_id == "cup-zacca"
        assert c.gestor == "Thiago M."

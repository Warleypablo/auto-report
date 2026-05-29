from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.auth import create_access_token
from app_settings import Settings, get_settings
from db import get_session
from models import AdInsight, Cliente, Criativo, CriativoThumb, Usuario, UsuarioCliente
from models.base import Base
from models.cliente import Categoria
from models.criativo import RedeAnuncio, ThumbStatus

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"
_SETTINGS = Settings(database_url=TEST_DB_URL)


@pytest.fixture
def app_with_db():
    engine = create_engine(TEST_DB_URL)
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
        return _SETTINGS

    app.dependency_overrides[get_session] = s_dep
    app.dependency_overrides[get_settings] = cfg_dep
    return app, TS


def _token(user: Usuario) -> str:
    return create_access_token(
        user.id, is_admin=user.is_admin,
        secret=_SETTINGS.jwt_secret, algorithm=_SETTINGS.jwt_algorithm,
        expiry_hours=_SETTINGS.jwt_expiry_hours,
    )


def _seed(TS):
    with TS() as s:
        admin = Usuario(email=f"a-{uuid.uuid4().hex[:8]}@x.com", nome="A",
                        senha_hash="x", is_admin=True, ativo=True)
        s.add(admin)
        c = Cliente(slug="loja", nome="Loja", categoria=Categoria.ECOMMERCE,
                    gestor="Ana", ativo=True)
        s.add(c)
        s.flush()
        cr = Criativo(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="A1", nome="Ad 1",
                      tipo="video", preview_link="https://fb/p", thumb_status=ThumbStatus.OK)
        s.add(cr)
        s.flush()
        s.add(CriativoThumb(criativo_id=cr.id, conteudo=b"\xff\xd8\xff\xe0JFIF",
                            mime="image/jpeg"))
        s.add(AdInsight(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="A1",
                        dia=date(2026, 5, 1), investimento=Decimal(100),
                        faturamento=Decimal(400), conversoes=Decimal(10), leads=5,
                        impressoes=1000, clicks=50, video_3s=200, reach=800))
        s.commit()
        return admin.id, cr.id


def test_list_criativos_200(app_with_db):
    app, TS = app_with_db
    admin_id, criativo_id = _seed(TS)
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        tok = _token(admin)
    client = TestClient(app)
    r = client.get(
        "/gestor/criativos?de=2026-05-01&ate=2026-05-31",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1
    it = data["items"][0]
    assert it["ad_id"] == "A1"
    assert it["rede"] == "meta"
    assert it["roas"] == 4.0
    assert it["thumb_url"] == f"/api/gestor/criativos/{criativo_id}/thumb"


def test_list_criativos_sem_token_401(app_with_db):
    app, TS = app_with_db
    _seed(TS)
    client = TestClient(app)
    r = client.get("/gestor/criativos?de=2026-05-01&ate=2026-05-31")
    assert r.status_code == 401


def test_list_criativos_thumb_url_null_quando_status_nao_ok(app_with_db):
    app, TS = app_with_db
    with TS() as s:
        admin = Usuario(email=f"a-{uuid.uuid4().hex[:8]}@x.com", nome="A",
                        senha_hash="x", is_admin=True, ativo=True)
        s.add(admin)
        c = Cliente(slug="g", nome="G", categoria=Categoria.ECOMMERCE, ativo=True)
        s.add(c)
        s.flush()
        s.add(Criativo(cliente_id=c.id, rede=RedeAnuncio.GOOGLE, ad_id="G1",
                       tipo="search", thumb_status=ThumbStatus.SEM_IMAGEM))
        s.add(AdInsight(cliente_id=c.id, rede=RedeAnuncio.GOOGLE, ad_id="G1",
                        dia=date(2026, 5, 1), investimento=Decimal(10),
                        faturamento=Decimal(0), conversoes=Decimal(0),
                        impressoes=100, clicks=2))
        s.commit()
        tok = _token(admin)
    client = TestClient(app)
    r = client.get("/gestor/criativos?de=2026-05-01&ate=2026-05-31",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    it = r.json()["items"][0]
    assert it["thumb_status"] == "sem_imagem"
    assert it["thumb_url"] is None


def test_thumb_200_bytes(app_with_db):
    app, TS = app_with_db
    admin_id, criativo_id = _seed(TS)
    with TS() as s:
        tok = _token(s.get(Usuario, admin_id))
    client = TestClient(app)
    r = client.get(f"/gestor/criativos/{criativo_id}/thumb",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    assert r.content == b"\xff\xd8\xff\xe0JFIF"
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert r.headers["etag"] == f'"{criativo_id}"'


def test_thumb_304_if_none_match(app_with_db):
    app, TS = app_with_db
    admin_id, criativo_id = _seed(TS)
    with TS() as s:
        tok = _token(s.get(Usuario, admin_id))
    client = TestClient(app)
    r = client.get(
        f"/gestor/criativos/{criativo_id}/thumb",
        headers={"Authorization": f"Bearer {tok}", "If-None-Match": f'"{criativo_id}"'},
    )
    assert r.status_code == 304


def test_thumb_404_criativo_inexistente(app_with_db):
    app, TS = app_with_db
    admin_id, _ = _seed(TS)
    with TS() as s:
        tok = _token(s.get(Usuario, admin_id))
    client = TestClient(app)
    r = client.get(f"/gestor/criativos/{uuid.uuid4()}/thumb",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404


def test_thumb_404_status_nao_ok(app_with_db):
    app, TS = app_with_db
    with TS() as s:
        admin = Usuario(email=f"a-{uuid.uuid4().hex[:8]}@x.com", nome="A",
                        senha_hash="x", is_admin=True, ativo=True)
        s.add(admin)
        c = Cliente(slug="g2", nome="G2", categoria=Categoria.ECOMMERCE, ativo=True)
        s.add(c)
        s.flush()
        cr = Criativo(cliente_id=c.id, rede=RedeAnuncio.GOOGLE, ad_id="G2",
                      thumb_status=ThumbStatus.SEM_IMAGEM)
        s.add(cr)
        s.commit()
        cr_id = cr.id
        tok = _token(admin)
    client = TestClient(app)
    r = client.get(f"/gestor/criativos/{cr_id}/thumb",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404


def test_thumb_404_sem_acesso(app_with_db):
    app, TS = app_with_db
    with TS() as s:
        gestor = Usuario(email=f"g-{uuid.uuid4().hex[:8]}@x.com", nome="G",
                         senha_hash="x", is_admin=False, ativo=True)
        s.add(gestor)
        c = Cliente(slug="alheio", nome="Alheio", categoria=Categoria.ECOMMERCE, ativo=True)
        s.add(c)
        s.flush()
        cr = Criativo(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="X1",
                      thumb_status=ThumbStatus.OK)
        s.add(cr)
        s.flush()
        s.add(CriativoThumb(criativo_id=cr.id, conteudo=b"img", mime="image/jpeg"))
        s.commit()
        cr_id = cr.id
        tok = _token(gestor)
    client = TestClient(app)
    r = client.get(f"/gestor/criativos/{cr_id}/thumb",
                   headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404

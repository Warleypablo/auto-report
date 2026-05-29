import re
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from api.gestor import router as gestor_router
from api.auth import require_auth
from db import get_session
from models import Base, Cliente, Categoria, Usuario, UsuarioCliente, ReportJob

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def client_e_ts():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine)
    with TS() as s:
        admin = Usuario(email="a@a.com", nome="A", senha_hash="x", is_admin=True, ativo=True)
        cli = Cliente(slug="acme", nome="Acme", categoria=Categoria.ECOMMERCE)
        s.add_all([admin, cli]); s.commit()
        admin_id = admin.id

    app = FastAPI()
    app.include_router(gestor_router, prefix="/gestor")

    def _sess():
        with TS() as s:
            yield s

    def _user():
        with TS() as s:
            return s.get(Usuario, admin_id)

    app.dependency_overrides[get_session] = _sess
    app.dependency_overrides[require_auth] = _user
    return TestClient(app), TS


def test_trigger_semanal_grava_semana_inicio(client_e_ts):
    client, TS = client_e_ts
    with patch("api.gestor.gerar_slides", create=True), \
         patch("services.report_slides.gerar_slides", return_value="https://x"):
        r = client.post("/gestor/reports/trigger", json={
            "slug": "acme", "mes": "2026-06", "frequencia": "SEMANAL", "semana_inicio": "2026-06-08"})
    assert r.status_code == 200, r.text
    with TS() as s:
        job = s.scalar(select(ReportJob))
        assert job.semana_inicio == "2026-06-08"


def test_trigger_semana_inicio_invalido_400(client_e_ts):
    client, _ = client_e_ts
    r = client.post("/gestor/reports/trigger", json={
        "slug": "acme", "mes": "2026-06", "frequencia": "SEMANAL", "semana_inicio": "08/06/2026"})
    assert r.status_code == 400

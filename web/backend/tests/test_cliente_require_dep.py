import uuid
from datetime import datetime, timedelta, timezone

from jose import jwt


def test_normalize_cnpj_removes_punctuation():
    from api.cliente import normalize_cnpj

    assert normalize_cnpj("12.345.678/0001-90") == "12345678000190"
    assert normalize_cnpj("  12345678000190  ") == "12345678000190"
    assert normalize_cnpj("abc12def345") == "12345"


def test_mask_cnpj():
    from api.cliente import mask_cnpj

    assert mask_cnpj("12345678000190") == "12.***.678/****-**"
    assert mask_cnpj("123") == "***"


def test_create_cliente_token_carries_kind():
    from api.cliente import create_cliente_token

    cid = uuid.uuid4()
    token = create_cliente_token(cid, secret="s", algorithm="HS256", expiry_hours=1)
    payload = jwt.decode(token, "s", algorithms=["HS256"])
    assert payload["sub"] == str(cid)
    assert payload["kind"] == "cliente"


def test_require_cliente_rejects_gestor_token():
    """Token com kind='gestor' não pode autenticar em rota de cliente."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.cliente import router as cliente_router
    from app_settings import get_settings

    settings = get_settings()
    app = FastAPI()
    app.include_router(cliente_router, prefix="/cliente")

    client = TestClient(app)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "kind": "gestor",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get("/cliente/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_require_cliente_rejects_missing_header():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.cliente import router as cliente_router

    app = FastAPI()
    app.include_router(cliente_router, prefix="/cliente")

    client = TestClient(app)
    r = client.get("/cliente/me")
    assert r.status_code == 401


def test_require_cliente_rejects_expired_token():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.cliente import router as cliente_router
    from app_settings import get_settings

    settings = get_settings()
    app = FastAPI()
    app.include_router(cliente_router, prefix="/cliente")

    client = TestClient(app)
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "kind": "cliente",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    r = client.get("/cliente/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401

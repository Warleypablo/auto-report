import pytest
from jose import jwt
from passlib.context import CryptContext


def test_jose_jwt_roundtrip():
    secret = "test-secret"
    payload = {"sub": "abc", "is_admin": False}
    token = jwt.encode(payload, secret, algorithm="HS256")
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    assert decoded["sub"] == "abc"
    assert decoded["is_admin"] is False


def test_passlib_bcrypt():
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed = ctx.hash("mypassword")
    assert ctx.verify("mypassword", hashed)
    assert not ctx.verify("wrong", hashed)


def test_models_import():
    from models import Usuario, UsuarioCliente, ReportJob, JobStatus
    assert JobStatus.PENDING == "pending"
    assert JobStatus.DONE == "done"


def test_schemas_import():
    from schemas.gestor import LoginRequest, LoginResponse, JobStatusResponse
    req = LoginRequest(email="a@b.com", senha="pass")
    assert req.email == "a@b.com"


import uuid as _uuid
from datetime import datetime as _datetime, timezone as _tz


def test_create_access_token_contains_sub():
    from api.auth import create_access_token
    uid = _uuid.uuid4()
    token = create_access_token(uid, is_admin=False, secret="s", algorithm="HS256", expiry_hours=1)
    from jose import jwt
    payload = jwt.decode(token, "s", algorithms=["HS256"])
    assert payload["sub"] == str(uid)
    assert payload["is_admin"] is False


def test_decode_token_returns_payload():
    from api.auth import create_access_token, decode_token
    uid = _uuid.uuid4()
    token = create_access_token(uid, is_admin=True, secret="s", algorithm="HS256", expiry_hours=1)
    payload = decode_token(token, secret="s", algorithm="HS256")
    assert payload["sub"] == str(uid)
    assert payload["is_admin"] is True


def test_verify_password():
    from api.auth import hash_password, verify_password
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed)
    assert not verify_password("wrong", hashed)


def test_gestor_router_mounts():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.auth import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)

    client = TestClient(app)
    # POST /auth/login with bad credentials → must NOT be 404 (route exists)
    r = client.post("/auth/login", json={"email": "x@x.com", "senha": "bad"})
    assert r.status_code != 404, f"Route not found: {r.status_code}"

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

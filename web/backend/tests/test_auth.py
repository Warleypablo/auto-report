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

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from app_settings import Settings, get_settings
from db import get_session
from models import Usuario
from schemas import LoginRequest, LoginResponse, UsuarioResponse

router = APIRouter()

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Pure utility functions ──────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_ctx.verify(plain, hashed)


def create_access_token(
    user_id: uuid.UUID,
    *,
    is_admin: bool,
    secret: str,
    algorithm: str,
    expiry_hours: int,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    payload = {"sub": str(user_id), "is_admin": is_admin, "exp": expire}
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_token(token: str, *, secret: str, algorithm: str) -> dict:
    """Raises JWTError on invalid or expired token."""
    return jwt.decode(token, secret, algorithms=[algorithm])


# ── FastAPI dependencies ───────────────────────────────────────────────────

def require_auth(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> Usuario:
    """Reads Bearer token from Authorization header, validates, returns user."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    uid = uuid.UUID(payload["sub"])
    user = session.get(Usuario, uid)
    if user is None or not user.ativo:
        raise HTTPException(status_code=401, detail="Usuário inativo ou inexistente")
    return user


def require_admin(user: Usuario = Depends(require_auth)) -> Usuario:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> LoginResponse:
    user = session.execute(
        select(Usuario).where(Usuario.email == body.email, Usuario.ativo == True)  # noqa: E712
    ).scalar_one_or_none()
    if user is None or not verify_password(body.senha, user.senha_hash):
        raise HTTPException(status_code=401, detail="Email ou senha inválidos")
    token = create_access_token(
        user.id,
        is_admin=user.is_admin,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expiry_hours=settings.jwt_expiry_hours,
    )
    return LoginResponse(
        token=token,
        usuario=UsuarioResponse(id=user.id, email=user.email, nome=user.nome, is_admin=user.is_admin),
    )


@router.post("/auth/logout")
def logout() -> dict:
    return {"ok": True}


@router.get("/auth/me", response_model=UsuarioResponse)
def me(user: Usuario = Depends(require_auth)) -> UsuarioResponse:
    return UsuarioResponse(id=user.id, email=user.email, nome=user.nome, is_admin=user.is_admin)

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app_settings import Settings, get_settings
from db import get_session
from models import Cliente
from schemas import ClienteLoginRequest, ClienteLoginResponse, ClientePublic

router = APIRouter()
_log = logging.getLogger(__name__)


def normalize_cnpj(raw: str) -> str:
    """Remove tudo que não for dígito."""
    return re.sub(r"\D", "", raw or "")


def mask_cnpj(cnpj_digits: str) -> str:
    """Mascara CNPJ para logging: '12345678000190' → '12.***.678/****-**'."""
    d = normalize_cnpj(cnpj_digits)
    if len(d) != 14:
        return "***"
    return f"{d[0:2]}.***.{d[5:8]}/****-**"


def create_cliente_token(
    cliente_id: uuid.UUID,
    *,
    secret: str,
    algorithm: str,
    expiry_hours: int,
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    payload = {"sub": str(cliente_id), "kind": "cliente", "exp": expire}
    return jwt.encode(payload, secret, algorithm=algorithm)


def require_cliente(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> Cliente:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token ausente")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("kind") != "cliente":
            raise HTTPException(status_code=401, detail="Token inválido para esta área")
        cid = uuid.UUID(payload["sub"])
    except HTTPException:
        raise
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")
    cliente = session.get(Cliente, cid)
    if cliente is None or not cliente.ativo:
        raise HTTPException(status_code=401, detail="Conta inativa ou inexistente")
    return cliente


@router.post("/auth/login", response_model=ClienteLoginResponse)
def login(
    body: ClienteLoginRequest,
    settings: Settings = Depends(get_settings),
    session: Session = Depends(get_session),
) -> ClienteLoginResponse:
    cnpj_digits = normalize_cnpj(body.cnpj)
    if len(cnpj_digits) < 11:
        _log.info("cliente_login cnpj_mask=*** result=invalid_format")
        raise HTTPException(status_code=401, detail="CNPJ inválido")

    rows = session.execute(
        text("""
            SELECT cc.task_id
            FROM staging.cup_clientes cc
            WHERE regexp_replace(COALESCE(cc.cnpj, ''), '[^0-9]', '', 'g') = :cnpj
        """),
        {"cnpj": cnpj_digits},
    ).all()

    masked = mask_cnpj(cnpj_digits)

    if not rows:
        _log.info(f"cliente_login cnpj_mask={masked} result=not_found")
        raise HTTPException(
            status_code=401,
            detail="CNPJ não encontrado. Verifique o número ou entre em contato com seu gestor.",
        )
    if len(rows) > 1:
        _log.info(f"cliente_login cnpj_mask={masked} result=multiple")
        raise HTTPException(
            status_code=401,
            detail="Múltiplas contas encontradas para este CNPJ. Fale com seu gestor.",
        )

    task_id = rows[0][0]
    cliente = session.execute(
        select(Cliente).where(Cliente.cup_task_id == task_id)
    ).scalar_one_or_none()

    if cliente is None:
        _log.info(f"cliente_login cnpj_mask={masked} result=broken_link")
        raise HTTPException(
            status_code=401,
            detail="Conta não disponível no momento. Fale com seu gestor.",
        )

    if not cliente.ativo:
        _log.info(f"cliente_login cnpj_mask={masked} result=inactive")
        raise HTTPException(status_code=401, detail="Conta inativa. Fale com seu gestor.")

    token = create_cliente_token(
        cliente.id,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
        expiry_hours=settings.jwt_expiry_hours,
    )

    _log.info(f"cliente_login cnpj_mask={masked} result=ok cliente_id={cliente.id}")

    return ClienteLoginResponse(
        token=token,
        cliente=ClientePublic(
            id=cliente.id,
            slug=cliente.slug,
            nome=cliente.nome,
            categoria=cliente.categoria,
            logo_url=cliente.logo_url,
            setor=cliente.setor,
        ),
    )


@router.get("/me", response_model=ClientePublic)
def me(cliente: Cliente = Depends(require_cliente)) -> ClientePublic:
    return ClientePublic(
        id=cliente.id,
        slug=cliente.slug,
        nome=cliente.nome,
        categoria=cliente.categoria,
        logo_url=cliente.logo_url,
        setor=cliente.setor,
    )

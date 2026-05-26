from __future__ import annotations

import logging
import re
import secrets
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from jose import JWTError, jwt
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session

from app_settings import Settings, get_settings
from db import get_session
from models import Cliente
from schemas import ClienteLoginRequest, ClienteLoginResponse, ClientePublic
from services.metricas import build_breakdown, build_timeline, meses_disponiveis_for_cliente
from services.cliente_highlight import compute_highlight as _compute_highlight

router = APIRouter()
_log = logging.getLogger(__name__)


def normalize_cnpj(raw: str) -> str:
    """Remove tudo que não for dígito."""
    return re.sub(r"\D", "", raw or "")


_SUFIXOS_JURIDICOS_RE = re.compile(
    r"\s+(ltda|me|mei|epp|eireli|s\.?a\.?|sa|inc\.?|corp\.?)\s*\.?\s*$",
    re.IGNORECASE,
)


def normalize_nome(s: str | None) -> str:
    """Match tolerante: sem acentos, lower, sem sufixos jurídicos, sem pontuação.

    Mesma normalização usada pelo automatch do admin (api/gestor.py).
    Duplicada aqui pra evitar import circular; alinhar se um lado mudar.
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = _SUFIXOS_JURIDICOS_RE.sub("", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


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

    # Senha global — comparação constant-time para não vazar por timing.
    if not secrets.compare_digest(body.senha or "", settings.cliente_password):
        _log.info(f"cliente_login cnpj_mask={mask_cnpj(cnpj_digits)} result=wrong_password")
        raise HTTPException(status_code=401, detail="CNPJ ou senha inválidos.")

    rows = session.execute(
        text("""
            SELECT cc.task_id, cc.nome
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

    task_id, cup_nome = rows[0]
    cliente = session.execute(
        select(Cliente).where(Cliente.cup_task_id == task_id)
    ).scalar_one_or_none()

    # Self-healing: vínculo cup_task_id pode estar NULL (migration original
    # rodou antes do pipeline popular staging.cup_clientes). Tenta match único
    # por nome normalizado e popula cup_task_id no DB.
    if cliente is None and cup_nome:
        nome_norm = normalize_nome(cup_nome)
        if nome_norm:
            candidatos = session.execute(
                select(Cliente).where(
                    Cliente.ativo == True,  # noqa: E712
                    Cliente.cup_task_id.is_(None),
                )
            ).scalars().all()
            matches = [c for c in candidatos if normalize_nome(c.nome) == nome_norm]
            if len(matches) == 1:
                cliente = matches[0]
                session.execute(
                    update(Cliente).where(Cliente.id == cliente.id).values(cup_task_id=task_id)
                )
                session.commit()
                _log.info(
                    f"cliente_login cnpj_mask={masked} result=auto_linked "
                    f"cliente_id={cliente.id} task_id={task_id}"
                )

    if cliente is None:
        _log.info(f"cliente_login cnpj_mask={masked} result=broken_link cup_nome={cup_nome!r}")
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


@router.post("/auth/logout", status_code=204)
def logout(_cliente: Cliente = Depends(require_cliente)) -> None:
    return None


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


@router.get("/metricas/timeline")
def metricas_timeline(
    meses: int = Query(12, ge=1, le=36),
    cliente: Cliente = Depends(require_cliente),
    session: Session = Depends(get_session),
) -> dict:
    return {"items": build_timeline(cliente.id, meses, session)}


@router.get("/metricas/breakdown")
def metricas_breakdown(
    mes: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
    cliente: Cliente = Depends(require_cliente),
    session: Session = Depends(get_session),
) -> dict:
    return build_breakdown(cliente.id, mes, session)


@router.get("/metricas/meses-disponiveis")
def metricas_meses_disponiveis(
    cliente: Cliente = Depends(require_cliente),
    session: Session = Depends(get_session),
) -> dict:
    return {"meses": meses_disponiveis_for_cliente(cliente.id, session)}


@router.get("/metricas/highlight")
def metricas_highlight(
    cliente: Cliente = Depends(require_cliente),
    session: Session = Depends(get_session),
) -> dict:
    timeline = build_timeline(cliente.id, 12, session)
    return {"highlight": _compute_highlight(timeline)}

# web/backend/tests/test_turbomax.py
import uuid
import pytest
from unittest.mock import MagicMock

from db import SessionLocal
from models import Cliente, Usuario, UsuarioCliente
from models.cliente import Categoria


@pytest.fixture
def db_cliente():
    slug = f"turbomax-test-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as s:
        c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE)
        s.add(c)
        s.commit()
        cid = c.id
    yield slug, cid
    with SessionLocal() as s:
        c = s.get(Cliente, cid)
        if c:
            s.delete(c)
            s.commit()


@pytest.fixture
def db_gestor(db_cliente):
    slug, cid = db_cliente
    uid = uuid.uuid4()
    with SessionLocal() as s:
        u = Usuario(id=uid, email=f"{uid.hex[:8]}@test.com", senha_hash="x", nome="Test Gestor", is_admin=False)
        s.add(u)
        s.commit()
    yield uid, slug, cid
    with SessionLocal() as s:
        u = s.get(Usuario, uid)
        if u:
            s.delete(u)
            s.commit()


def test_check_acesso_admin_ve_qualquer_cliente(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True
    with SessionLocal() as s:
        from api.turbomax import _check_acesso_cliente
        c = _check_acesso_cliente(slug, admin, s)
        assert c.slug == slug


def test_check_acesso_gestor_sem_atribuicao_falha(db_gestor):
    uid, slug, cid = db_gestor
    user = MagicMock()
    user.is_admin = False
    user.id = uid
    with SessionLocal() as s:
        from api.turbomax import _check_acesso_cliente
        with pytest.raises(ValueError, match="não tem acesso"):
            _check_acesso_cliente(slug, user, s)


def test_check_acesso_gestor_com_atribuicao_ok(db_gestor):
    uid, slug, cid = db_gestor
    with SessionLocal() as s:
        uc = UsuarioCliente(usuario_id=uid, cliente_id=cid)
        s.add(uc)
        s.commit()
    user = MagicMock()
    user.is_admin = False
    user.id = uid
    with SessionLocal() as s:
        from api.turbomax import _check_acesso_cliente
        c = _check_acesso_cliente(slug, user, s)
        assert c.slug == slug
    # cleanup
    with SessionLocal() as s:
        from sqlalchemy import select as _sel
        uc = s.scalar(_sel(UsuarioCliente).where(
            UsuarioCliente.usuario_id == uid, UsuarioCliente.cliente_id == cid
        ))
        if uc:
            s.delete(uc)
            s.commit()


def test_check_acesso_cliente_inexistente_falha():
    user = MagicMock()
    user.is_admin = True
    with SessionLocal() as s:
        from api.turbomax import _check_acesso_cliente
        with pytest.raises(ValueError, match="não encontrado"):
            _check_acesso_cliente("slug-que-nao-existe-xyz", user, s)

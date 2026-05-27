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


# ─── Tests for DB tools ──────────────────────────────────────────────────────

from decimal import Decimal
from datetime import date as _date
from models.snapshot import Snapshot, Frequencia


@pytest.fixture
def db_snapshot(db_cliente):
    slug, cid = db_cliente
    with SessionLocal() as s:
        snap = Snapshot(
            cliente_id=cid,
            periodo_inicio=_date(2026, 5, 1),
            periodo_fim=_date(2026, 5, 31),
            frequencia=Frequencia.MENSAL,
            faturamento=Decimal("85000"),
            investimento=Decimal("22000"),
            roas=Decimal("3.86"),
            metricas_detalhadas={"meta": {"faturamento": 60000, "investimento": 15000, "roas": 4.0}},
            raw_dados={},
        )
        s.add(snap)
        s.commit()
        sid = snap.id
    yield slug, cid, sid
    with SessionLocal() as s:
        snap = s.get(Snapshot, sid)
        if snap:
            s.delete(snap)
            s.commit()


def test_listar_clientes_admin_ve_todos(db_snapshot):
    slug, _, _ = db_snapshot
    admin = MagicMock()
    admin.is_admin = True
    with SessionLocal() as s:
        from api.turbomax import _listar_clientes
        result = _listar_clientes(admin, s)
    slugs = [r["slug"] for r in result]
    assert slug in slugs


def test_get_metricas_cliente_retorna_dados(db_snapshot):
    slug, _, _ = db_snapshot
    admin = MagicMock()
    admin.is_admin = True
    with SessionLocal() as s:
        from api.turbomax import _get_metricas_cliente
        result = _get_metricas_cliente(slug, "2026-05", admin, s)
    assert result["faturamento"] == 85000.0
    assert result["roas"] == pytest.approx(3.86, rel=1e-3)
    assert result["meta"]["faturamento"] == 60000


def test_get_metricas_cliente_sem_snapshot_retorna_erro(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True
    with SessionLocal() as s:
        from api.turbomax import _get_metricas_cliente
        result = _get_metricas_cliente(slug, "2020-01", admin, s)
    assert "erro" in result


def test_get_historico_cliente_ordem_cronologica(db_snapshot):
    slug, cid, _ = db_snapshot
    with SessionLocal() as s:
        snap2 = Snapshot(
            cliente_id=cid,
            periodo_inicio=_date(2026, 4, 1),
            periodo_fim=_date(2026, 4, 30),
            frequencia=Frequencia.MENSAL,
            faturamento=Decimal("75000"),
            investimento=Decimal("20000"),
            roas=Decimal("3.75"),
            metricas_detalhadas={},
            raw_dados={},
        )
        s.add(snap2)
        s.commit()
        sid2 = snap2.id
    admin = MagicMock()
    admin.is_admin = True
    with SessionLocal() as s:
        from api.turbomax import _get_historico_cliente
        result = _get_historico_cliente(slug, 6, admin, s)
    meses = [r["mes"] for r in result]
    assert meses == sorted(meses)
    with SessionLocal() as s:
        snap = s.get(Snapshot, sid2)
        if snap:
            s.delete(snap)
            s.commit()


def test_comparar_clientes_ranking_e_media(db_snapshot):
    admin = MagicMock()
    admin.is_admin = True
    slug, _, _ = db_snapshot
    with SessionLocal() as s:
        from api.turbomax import _comparar_clientes
        result = _comparar_clientes(None, "roas", "2026-05", admin, s)
    assert "ranking" in result
    assert "media_carteira" in result
    rank_slugs = [r["slug"] for r in result["ranking"]]
    assert slug in rank_slugs


# ─── Tests for external API tools ────────────────────────────────────────────

from unittest.mock import patch


def test_buscar_campanhas_meta_sem_id_meta(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_meta_ads = None

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core):
            from api.turbomax import _buscar_campanhas_meta
            result = _buscar_campanhas_meta(slug, "2026-05-01", "2026-05-31", admin, s)

    assert "erro" in result
    assert "Meta Ads" in result["erro"]


def test_buscar_campanhas_meta_retorna_lista(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_meta_ads = "act_12345"

    fake_response = {
        "data": [
            {
                "campaign_id": "111",
                "campaign_name": "Prospecção",
                "spend": "5000",
                "impressions": "200000",
                "clicks": "4000",
                "actions": [{"action_type": "purchase", "value": "15"}],
                "action_values": [{"action_type": "purchase", "value": "20000"}],
            }
        ]
    }

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core), \
             patch("api.turbomax.requests.get") as mock_get:
            mock_get.return_value.json.return_value = fake_response
            mock_get.return_value.raise_for_status = MagicMock()
            from api.turbomax import _buscar_campanhas_meta
            result = _buscar_campanhas_meta(slug, "2026-05-01", "2026-05-31", admin, s)

    assert len(result["campanhas"]) == 1
    assert result["campanhas"][0]["nome"] == "Prospecção"
    assert result["campanhas"][0]["purchases"] == 15


def test_buscar_campanhas_google_sem_id_google(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_google_ads = None

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core):
            from api.turbomax import _buscar_campanhas_google
            result = _buscar_campanhas_google(slug, "2026-05-01", "2026-05-31", admin, s)

    assert "erro" in result
    assert "Google Ads" in result["erro"]


def test_execute_tool_nao_reconhecida():
    admin = MagicMock()
    admin.is_admin = True
    with SessionLocal() as s:
        from api.turbomax import _execute_tool
        result = _execute_tool("ferramenta_inexistente", {}, admin, s)
    assert "erro" in result

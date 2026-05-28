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


def test_buscar_campanhas_meta_api_error(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_meta_ads = "act_12345"

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core), \
             patch("api.turbomax.requests.get") as mock_get:
            import requests as req_lib
            mock_get.side_effect = req_lib.RequestException("timeout")
            from api.turbomax import _buscar_campanhas_meta
            result = _buscar_campanhas_meta(slug, "2026-05-01", "2026-05-31", admin, s)

    assert "erro" in result
    assert "Falha" in result["erro"]


def test_buscar_campanhas_google_mock_client(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_google_ads = "1234567890"

    fake_row = MagicMock()
    fake_row.campaign.id = 99
    fake_row.campaign.name = "Brand Search"
    fake_row.campaign.status.name = "ENABLED"
    fake_row.metrics.cost_micros = 2_000_000
    fake_row.metrics.impressions = 10000
    fake_row.metrics.clicks = 500
    fake_row.metrics.conversions = 20.0
    fake_row.metrics.conversions_value = 6000.0

    fake_ga_service = MagicMock()
    fake_ga_service.search.return_value = [fake_row]
    fake_client = MagicMock()
    fake_client.get_service.return_value = fake_ga_service

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core), \
             patch("core.cred_manager._build_google_ads_client", return_value=fake_client):
            from api.turbomax import _buscar_campanhas_google
            result = _buscar_campanhas_google(slug, "2026-05-01", "2026-05-31", admin, s)

    assert len(result["campanhas"]) == 1
    assert result["campanhas"][0]["nome"] == "Brand Search"
    assert result["campanhas"][0]["spend"] == 2.0


def test_buscar_anuncios_meta_sem_id_meta(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_meta_ads = None

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core):
            from api.turbomax import _buscar_anuncios_meta
            result = _buscar_anuncios_meta(slug, "2026-05-01", "2026-05-31", admin, s)

    assert "erro" in result
    assert "Meta Ads" in result["erro"]


def test_buscar_anuncios_meta_retorna_lista(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_meta_ads = "act_12345"

    fake_response = {
        "data": [
            {
                "ad_id": "222",
                "ad_name": "UGC_Produto_V1",
                "adset_name": "Prospecção Broad",
                "campaign_name": "Prospecção_CBO",
                "spend": "3000",
                "impressions": "120000",
                "clicks": "2400",
                "reach": "100000",
                "frequency": "1.2",
                "actions": [{"action_type": "purchase", "value": "12"}],
                "action_values": [{"action_type": "purchase", "value": "12000"}],
                "video_p3_watched_actions": [{"action_type": "video_view", "value": "30000"}],
            }
        ]
    }

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core), \
             patch("api.turbomax.requests.get") as mock_get:
            mock_get.return_value.json.return_value = fake_response
            mock_get.return_value.raise_for_status = MagicMock()
            from api.turbomax import _buscar_anuncios_meta
            result = _buscar_anuncios_meta(slug, "2026-05-01", "2026-05-31", admin, s)

    assert len(result["anuncios"]) == 1
    ad = result["anuncios"][0]
    assert ad["nome"] == "UGC_Produto_V1"
    assert ad["purchases"] == 12
    assert ad["hook_rate"] == pytest.approx(25.0, rel=1e-2)
    assert ad["purchase_roas"] == pytest.approx(4.0, rel=1e-2)


# ─── Tests for endpoint /chat ────────────────────────────────────────────────

from fastapi.testclient import TestClient
from fastapi import FastAPI
from api.auth import create_access_token


def _make_test_app():
    from api.turbomax import router as turbomax_router
    app = FastAPI()
    # The router already has prefix="/turbomax", so we just need the parent /gestor prefix
    app.include_router(turbomax_router, prefix="/gestor")
    return app


def test_chat_endpoint_sem_api_key(db_gestor):
    uid, slug, cid = db_gestor

    # Atribuir cliente ao gestor
    with SessionLocal() as s:
        uc = UsuarioCliente(usuario_id=uid, cliente_id=cid)
        s.add(uc)
        s.commit()

    from app_settings import get_settings
    settings = get_settings()
    token = create_access_token(uid, is_admin=False,
                                secret=settings.jwt_secret,
                                algorithm=settings.jwt_algorithm,
                                expiry_hours=1)

    app = _make_test_app()
    client = TestClient(app)

    with patch("api.turbomax.get_settings") as mock_settings:
        mock_settings.return_value.anthropic_api_key = ""
        mock_settings.return_value.jwt_secret = settings.jwt_secret
        mock_settings.return_value.jwt_algorithm = settings.jwt_algorithm
        resp = client.post(
            "/gestor/turbomax/chat",
            json={"messages": [{"role": "user", "content": "Olá"}]},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 503

    # Cleanup
    with SessionLocal() as s:
        from sqlalchemy import select as _sel
        uc = s.scalar(_sel(UsuarioCliente).where(
            UsuarioCliente.usuario_id == uid, UsuarioCliente.cliente_id == cid
        ))
        if uc:
            s.delete(uc)
            s.commit()


def test_chat_endpoint_com_mock_claude(db_gestor):
    uid, slug, cid = db_gestor

    # Atribuir cliente ao gestor
    with SessionLocal() as s:
        uc = UsuarioCliente(usuario_id=uid, cliente_id=cid)
        s.add(uc)
        s.commit()

    from app_settings import get_settings
    settings = get_settings()
    token = create_access_token(uid, is_admin=False,
                                secret=settings.jwt_secret,
                                algorithm=settings.jwt_algorithm,
                                expiry_hours=1)

    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = "Olá! Sou o TurboMax."
    fake_response = MagicMock()
    fake_response.stop_reason = "end_turn"
    fake_response.content = [fake_block]

    fake_anthropic_client = MagicMock()
    fake_anthropic_client.messages.create.return_value = fake_response

    with patch("anthropic.Anthropic", return_value=fake_anthropic_client), \
         patch("api.turbomax.get_settings") as mock_settings:
        mock_settings.return_value.anthropic_api_key = "sk-test"
        mock_settings.return_value.jwt_secret = settings.jwt_secret
        mock_settings.return_value.jwt_algorithm = settings.jwt_algorithm

        app = _make_test_app()
        client = TestClient(app)
        resp = client.post(
            "/gestor/turbomax/chat",
            json={"messages": [{"role": "user", "content": "Olá"}]},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["reply"] == "Olá! Sou o TurboMax."

    # Cleanup
    with SessionLocal() as s:
        from sqlalchemy import select as _sel
        uc = s.scalar(_sel(UsuarioCliente).where(
            UsuarioCliente.usuario_id == uid, UsuarioCliente.cliente_id == cid
        ))
        if uc:
            s.delete(uc)
            s.commit()


def test_buscar_anuncios_google_sem_id_google(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_google_ads = None

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core):
            from api.turbomax import _buscar_anuncios_google
            result = _buscar_anuncios_google(slug, "2026-05-01", "2026-05-31", admin, s)

    assert "erro" in result
    assert "Google Ads" in result["erro"]


def test_buscar_anuncios_google_mock_client(db_cliente):
    slug, _ = db_cliente
    admin = MagicMock()
    admin.is_admin = True

    fake_core = MagicMock()
    fake_core.id_google_ads = "1234567890"

    fake_row = MagicMock()
    fake_row.ad_group_ad.ad.id = 555
    fake_row.ad_group_ad.ad.name = "Headline_Produto_V2"
    fake_row.ad_group_ad.ad.type_.name = "EXPANDED_TEXT_AD"
    fake_row.ad_group.name = "Produto - Exact"
    fake_row.campaign.name = "Search_Brand"
    fake_row.metrics.cost_micros = 1_500_000
    fake_row.metrics.impressions = 8000
    fake_row.metrics.clicks = 400
    fake_row.metrics.conversions = 18.0
    fake_row.metrics.conversions_value = 5.4

    fake_ga_service = MagicMock()
    fake_ga_service.search.return_value = [fake_row]
    fake_client = MagicMock()
    fake_client.get_service.return_value = fake_ga_service

    with SessionLocal() as s:
        with patch("api.turbomax._get_cliente_core", return_value=fake_core), \
             patch("core.cred_manager._build_google_ads_client", return_value=fake_client):
            from api.turbomax import _buscar_anuncios_google
            result = _buscar_anuncios_google(slug, "2026-05-01", "2026-05-31", admin, s)

    assert len(result["anuncios"]) == 1
    ad = result["anuncios"][0]
    assert ad["nome"] == "Headline_Produto_V2"
    assert ad["spend"] == 1.5
    assert ad["roas"] == pytest.approx(3.6, rel=1e-2)  # 5.4/1.5
    assert ad["ctr"] == pytest.approx(5.0, rel=1e-2)
    # fake_row.metrics.cost_micros = 1_500_000 → cost = 1.5
    # fake_row.metrics.impressions = 8000
    # cpm = 1.5 / 8000 * 1000 = 0.1875 → rounds to 0.19
    assert ad["cpm"] == pytest.approx(0.19, rel=1e-2)

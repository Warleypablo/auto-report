"""Fallback do report para o banco quando o cliente não está na Planilha Central.

Cliente cadastrado via sistema (POST /clientes) existe só em public.clientes, não
na Planilha Central. O report (report_slides) deve então montar o core.Cliente a
partir do registro do banco em vez de falhar com "não encontrado na Planilha".
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from models.base import Base
from models.cliente import Cliente, Categoria

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture(scope="module")
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.drop_all(engine)


@pytest.fixture
def limpa_clientes(TS):
    with TS() as s:
        s.execute(delete(Cliente))
        s.commit()
    return TS


@pytest.fixture
def core_settings():
    return SimpleNamespace(CENTRAL_SHEET_URL="http://sheet", CENTRAL_TAB_NAME="Clientes")


def _db_cliente_ns(**kw):
    """Imita um registro de public.clientes (duck-typed), sem tocar o banco."""
    base = dict(
        nome="Bewo 2",
        categoria=SimpleNamespace(value="E-commerce"),  # imita o Enum do banco
        painel_url="",
        pasta_url="https://drive/x",
        id_google_ads="",
        id_meta_ads="123",
        id_ga4=None,
        slug="bewo-2",
    )
    base.update(kw)
    return SimpleNamespace(**base)


# ── _core_cliente_from_db: mapeamento puro banco → core.Cliente ────────────────

def test_core_cliente_from_db_mapeia_campos():
    from services.report_slides import _core_cliente_from_db

    c = _core_cliente_from_db(_db_cliente_ns())

    assert c.nome == "Bewo 2"
    assert c.categoria == "E-commerce"
    assert c.id_meta_ads == "123"
    assert c.pasta_url == "https://drive/x"


def test_core_cliente_from_db_none_vira_string_vazia():
    # core.Cliente.__post_init__ faz .strip() — None quebraria; precisa virar "".
    from services.report_slides import _core_cliente_from_db

    c = _core_cliente_from_db(_db_cliente_ns(id_ga4=None, id_google_ads=None))

    assert c.id_ga4 == ""
    assert c.id_google_ads == ""


def test_core_cliente_from_db_categoria_resolve_handler():
    from services.report_slides import _core_cliente_from_db
    from core.categorias import get_handler

    c = _core_cliente_from_db(_db_cliente_ns(categoria=SimpleNamespace(value="E-commerce")))

    assert get_handler(c.categoria) is not None


def test_core_cliente_from_db_extras_vazio_nao_quebra_status():
    from services.report_slides import _core_cliente_from_db
    from core.status import set_status

    c = _core_cliente_from_db(_db_cliente_ns())

    assert c.extras == {}
    set_status(c, "GERADO ✅")  # sem metadados de planilha → no-op, não pode levantar


# ── _resolver_cliente: planilha primeiro, banco como fallback ──────────────────

def test_resolver_cliente_usa_planilha_quando_existe(core_settings):
    from services.report_slides import _resolver_cliente

    sentinela = object()

    def _boom():
        raise AssertionError("não deveria tocar o banco quando a planilha tem o cliente")

    with patch("core.leitura_central.fetch_clientes", return_value=[sentinela]):
        out = _resolver_cliente("bewo-2", "Bewo 2", core_settings, session_factory=_boom)

    assert out is sentinela


def test_resolver_cliente_fallback_banco(limpa_clientes, core_settings):
    from services.report_slides import _resolver_cliente

    TS = limpa_clientes
    with TS() as s:
        s.add(Cliente(
            slug="bewo-2", nome="Bewo 2", categoria=Categoria.ECOMMERCE,
            id_meta_ads="123", pasta_url="https://drive/x",
        ))
        s.commit()

    with patch("core.leitura_central.fetch_clientes", return_value=[]):
        out = _resolver_cliente("bewo-2", "Bewo 2", core_settings, session_factory=TS)

    assert out.nome == "Bewo 2"
    assert out.categoria == "E-commerce"
    assert out.id_meta_ads == "123"


def test_resolver_cliente_nao_acha_em_lugar_nenhum(limpa_clientes, core_settings):
    from services.report_slides import _resolver_cliente

    with patch("core.leitura_central.fetch_clientes", return_value=[]):
        with pytest.raises(ValueError, match="não encontrado"):
            _resolver_cliente(
                "inexistente", "Inexistente", core_settings, session_factory=limpa_clientes
            )

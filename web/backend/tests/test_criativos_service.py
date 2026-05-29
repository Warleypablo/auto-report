from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import AdInsight, Cliente, Criativo, Usuario, UsuarioCliente
from models.base import Base
from models.cliente import Categoria
from models.criativo import RedeAnuncio, ThumbStatus
from services.criativos import agregar_criativos

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def db():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    TS = sessionmaker(bind=engine)
    yield TS


def _admin(s) -> Usuario:
    u = Usuario(email=f"adm-{uuid.uuid4().hex[:8]}@x.com", nome="Admin",
                senha_hash="x", is_admin=True, ativo=True)
    s.add(u)
    s.flush()
    return u


def _cliente(s, *, slug, nome="Cli", gestor="Gabriel Taufner", categoria=Categoria.ECOMMERCE,
             ativo=True) -> Cliente:
    c = Cliente(slug=slug, nome=nome, categoria=categoria, gestor=gestor, ativo=ativo)
    s.add(c)
    s.flush()
    return c


def _criativo(s, *, cliente, rede, ad_id, nome="Ad", tipo="video",
              thumb_status=ThumbStatus.OK) -> Criativo:
    cr = Criativo(cliente_id=cliente.id, rede=rede, ad_id=ad_id, nome=nome, tipo=tipo,
                  preview_link="https://fb.com/p", thumb_status=thumb_status)
    s.add(cr)
    s.flush()
    return cr


def _insight(s, *, cliente, rede, ad_id, dia, investimento=0, faturamento=0,
             conversoes=0, leads=None, impressoes=0, clicks=0, video_3s=None, reach=None):
    s.add(AdInsight(
        cliente_id=cliente.id, rede=rede, ad_id=ad_id, dia=dia,
        investimento=Decimal(investimento), faturamento=Decimal(faturamento),
        conversoes=Decimal(conversoes), leads=leads, impressoes=impressoes,
        clicks=clicks, video_3s=video_3s, reach=reach,
    ))


def test_agrega_dois_dias_em_uma_linha(db):
    TS = db
    with TS() as s:
        admin = _admin(s)
        c = _cliente(s, slug="loja")
        _criativo(s, cliente=c, rede=RedeAnuncio.META, ad_id="A1", nome="Black Friday")
        _insight(s, cliente=c, rede=RedeAnuncio.META, ad_id="A1", dia=date(2026, 5, 1),
                 investimento=100, faturamento=400, conversoes=10, leads=5,
                 impressoes=1000, clicks=50, video_3s=200, reach=800)
        _insight(s, cliente=c, rede=RedeAnuncio.META, ad_id="A1", dia=date(2026, 5, 2),
                 investimento=100, faturamento=500, conversoes=10, leads=5,
                 impressoes=1000, clicks=50, video_3s=200, reach=900)
        s.commit()
        admin_id = admin.id

    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, total = agregar_criativos(
            s, de=date(2026, 5, 1), ate=date(2026, 5, 31),
            rede="todos", categorias=None, gestor=None, cliente_slug=None,
            fat_min=None, fat_max=None, inv_min=None, inv_max=None,
            cli_fat_min=None, cli_fat_max=None, cli_inv_min=None, cli_inv_max=None,
            order_by="roas", limit=50, offset=0, user=admin,
        )

    assert total == 1
    assert len(items) == 1
    it = items[0]
    assert it.ad_id == "A1"
    assert it.rede == "meta"
    assert it.cliente_slug == "loja"
    assert it.cliente_nome == "Cli"
    assert it.categoria == "E-commerce"
    assert it.gestor_nome == "Gabriel Taufner"
    assert it.nome == "Black Friday"
    assert it.tipo == "video"
    assert it.thumb_status == "ok"
    assert it.investimento == 200.0
    assert it.faturamento == 900.0
    assert it.impressoes == 2000
    assert it.clicks == 100
    assert it.conversoes == 20.0
    assert it.leads == 10
    assert it.roas == 4.5                 # 900 / 200
    assert it.ctr == pytest.approx(0.05)  # 100 / 2000
    assert it.cpa == pytest.approx(10.0)  # 200 / 20
    assert it.cpl == pytest.approx(20.0)  # 200 / 10
    assert it.hook_rate == pytest.approx(0.2)   # 400 / 2000
    assert it.frequency == pytest.approx(2000 / 1700)  # impressoes / reach


def test_derivadas_none_quando_denominador_zero(db):
    TS = db
    with TS() as s:
        admin = _admin(s)
        c = _cliente(s, slug="zero")
        _criativo(s, cliente=c, rede=RedeAnuncio.GOOGLE, ad_id="G1",
                  tipo="search", thumb_status=ThumbStatus.SEM_IMAGEM)
        _insight(s, cliente=c, rede=RedeAnuncio.GOOGLE, ad_id="G1", dia=date(2026, 5, 3),
                 investimento=50, faturamento=0, conversoes=0, leads=None,
                 impressoes=0, clicks=0, video_3s=None, reach=None)
        s.commit()
        admin_id = admin.id

    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, total = agregar_criativos(
            s, de=date(2026, 5, 1), ate=date(2026, 5, 31),
            rede="todos", categorias=None, gestor=None, cliente_slug=None,
            fat_min=None, fat_max=None, inv_min=None, inv_max=None,
            cli_fat_min=None, cli_fat_max=None, cli_inv_min=None, cli_inv_max=None,
            order_by="roas", limit=50, offset=0, user=admin,
        )

    assert total == 1
    it = items[0]
    assert it.rede == "google"
    assert it.investimento == 50.0
    assert it.faturamento == 0.0
    assert it.roas == 0.0        # faturamento/investimento = 0/50 = 0.0 (investimento>0 → não None)
    assert it.ctr is None        # impressoes == 0
    assert it.cpa is None        # conversoes == 0
    assert it.cpl is None        # leads soma None
    assert it.hook_rate is None  # video_3s None
    assert it.frequency is None  # reach None

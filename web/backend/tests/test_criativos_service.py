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
        items, total, _totais = agregar_criativos(
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
        items, total, _totais = agregar_criativos(
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


def _seed_dois_clientes(s):
    admin = _admin(s)
    c1 = _cliente(s, slug="ecom", nome="Ecom", gestor="Ana", categoria=Categoria.ECOMMERCE)
    c2 = _cliente(s, slug="lead", nome="Lead", gestor="Bruno", categoria=Categoria.LEAD_COM_SITE)
    _criativo(s, cliente=c1, rede=RedeAnuncio.META, ad_id="M1")
    _criativo(s, cliente=c1, rede=RedeAnuncio.GOOGLE, ad_id="G1", tipo="search")
    _criativo(s, cliente=c2, rede=RedeAnuncio.META, ad_id="M2")
    # c1/META: inv 100 fat 1000
    _insight(s, cliente=c1, rede=RedeAnuncio.META, ad_id="M1", dia=date(2026, 5, 1),
             investimento=100, faturamento=1000, impressoes=500, clicks=10)
    # c1/GOOGLE: inv 200 fat 300
    _insight(s, cliente=c1, rede=RedeAnuncio.GOOGLE, ad_id="G1", dia=date(2026, 5, 1),
             investimento=200, faturamento=300, impressoes=500, clicks=10)
    # c2/META: inv 50 fat 50
    _insight(s, cliente=c2, rede=RedeAnuncio.META, ad_id="M2", dia=date(2026, 5, 1),
             investimento=50, faturamento=50, impressoes=500, clicks=10)
    s.commit()
    return admin.id


def _run(s, admin, **over):
    kwargs = dict(
        de=date(2026, 5, 1), ate=date(2026, 5, 31), rede="todos", categorias=None,
        gestor=None, cliente_slug=None, fat_min=None, fat_max=None, inv_min=None,
        inv_max=None, cli_fat_min=None, cli_fat_max=None, cli_inv_min=None,
        cli_inv_max=None, order_by="roas", limit=50, offset=0, user=admin,
    )
    kwargs.update(over)
    items, total, _totais = agregar_criativos(s, **kwargs)
    return items, total


def test_filtro_rede_meta(db):
    TS = db
    with TS() as s:
        admin_id = _seed_dois_clientes(s)
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, total = _run(s, admin, rede="meta")
    assert total == 2
    assert {it.ad_id for it in items} == {"M1", "M2"}
    assert all(it.rede == "meta" for it in items)


def test_filtro_categoria(db):
    TS = db
    with TS() as s:
        admin_id = _seed_dois_clientes(s)
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, total = _run(s, admin, categorias=["ECOMMERCE"])
    assert {it.cliente_slug for it in items} == {"ecom"}
    assert total == 2  # M1 + G1


def test_filtro_gestor(db):
    TS = db
    with TS() as s:
        admin_id = _seed_dois_clientes(s)
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, total = _run(s, admin, gestor="Bruno")
    assert total == 1
    assert items[0].ad_id == "M2"


def test_filtro_cliente_slug(db):
    TS = db
    with TS() as s:
        admin_id = _seed_dois_clientes(s)
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, total = _run(s, admin, cliente_slug="lead")
    assert total == 1
    assert items[0].cliente_slug == "lead"


def test_faixa_faturamento_por_criativo(db):
    TS = db
    with TS() as s:
        admin_id = _seed_dois_clientes(s)
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        # só anúncios com faturamento somado >= 300 → M1 (1000) e G1 (300)
        items, total = _run(s, admin, fat_min=300)
    assert {it.ad_id for it in items} == {"M1", "G1"}
    assert total == 2


def test_faixa_investimento_por_cliente(db):
    TS = db
    with TS() as s:
        admin_id = _seed_dois_clientes(s)
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        # cliente ecom investe 300 no total (100+200); lead investe 50.
        # cli_inv_min=100 mantém só ecom (todos os anúncios dele).
        items, total = _run(s, admin, cli_inv_min=100)
    assert {it.cliente_slug for it in items} == {"ecom"}
    assert total == 2


def test_paginacao_total_e_limit(db):
    TS = db
    with TS() as s:
        admin = _admin(s)
        c = _cliente(s, slug="multi")
        for i in range(5):
            ad = f"AD{i}"
            _criativo(s, cliente=c, rede=RedeAnuncio.META, ad_id=ad)
            _insight(s, cliente=c, rede=RedeAnuncio.META, ad_id=ad, dia=date(2026, 5, 1),
                     investimento=10 * (i + 1), faturamento=100 * (i + 1),
                     impressoes=100, clicks=5)
        s.commit()
        admin_id = admin.id
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, total = _run(s, admin, order_by="faturamento", limit=2, offset=0)
    assert total == 5
    assert len(items) == 2
    # ordenado por faturamento DESC: AD4 (500), AD3 (400)
    assert [it.ad_id for it in items] == ["AD4", "AD3"]


def test_paginacao_offset(db):
    TS = db
    with TS() as s:
        admin = _admin(s)
        c = _cliente(s, slug="multi2")
        for i in range(5):
            ad = f"AD{i}"
            _criativo(s, cliente=c, rede=RedeAnuncio.META, ad_id=ad)
            _insight(s, cliente=c, rede=RedeAnuncio.META, ad_id=ad, dia=date(2026, 5, 1),
                     investimento=10, faturamento=100 * (i + 1), impressoes=100, clicks=5)
        s.commit()
        admin_id = admin.id
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, total = _run(s, admin, order_by="faturamento", limit=2, offset=2)
    assert total == 5
    # DESC: AD4,AD3,[AD2,AD1],AD0 → offset 2 pega AD2, AD1
    assert [it.ad_id for it in items] == ["AD2", "AD1"]


def test_order_by_investimento(db):
    TS = db
    with TS() as s:
        admin = _admin(s)
        c = _cliente(s, slug="ord")
        _criativo(s, cliente=c, rede=RedeAnuncio.META, ad_id="LO")
        _criativo(s, cliente=c, rede=RedeAnuncio.META, ad_id="HI")
        _insight(s, cliente=c, rede=RedeAnuncio.META, ad_id="LO", dia=date(2026, 5, 1),
                 investimento=10, faturamento=10, impressoes=100, clicks=5)
        _insight(s, cliente=c, rede=RedeAnuncio.META, ad_id="HI", dia=date(2026, 5, 1),
                 investimento=999, faturamento=10, impressoes=100, clicks=5)
        s.commit()
        admin_id = admin.id
    with TS() as s:
        admin = s.get(Usuario, admin_id)
        items, _ = _run(s, admin, order_by="investimento")
    assert [it.ad_id for it in items] == ["HI", "LO"]


def test_escopo_gestor_so_ve_seus_clientes(db):
    TS = db
    with TS() as s:
        c1 = _cliente(s, slug="meu")
        c2 = _cliente(s, slug="alheio")
        gestor = Usuario(email=f"g-{uuid.uuid4().hex[:8]}@x.com", nome="G",
                         senha_hash="x", is_admin=False, ativo=True)
        s.add(gestor)
        s.flush()
        s.add(UsuarioCliente(usuario_id=gestor.id, cliente_id=c1.id))
        _criativo(s, cliente=c1, rede=RedeAnuncio.META, ad_id="MEU")
        _criativo(s, cliente=c2, rede=RedeAnuncio.META, ad_id="ALHEIO")
        _insight(s, cliente=c1, rede=RedeAnuncio.META, ad_id="MEU", dia=date(2026, 5, 1),
                 investimento=10, faturamento=10, impressoes=100, clicks=5)
        _insight(s, cliente=c2, rede=RedeAnuncio.META, ad_id="ALHEIO", dia=date(2026, 5, 1),
                 investimento=10, faturamento=10, impressoes=100, clicks=5)
        s.commit()
        gestor_id = gestor.id
    with TS() as s:
        gestor = s.get(Usuario, gestor_id)
        items, total = _run(s, gestor)
    assert total == 1
    assert items[0].ad_id == "MEU"


def test_totais_somam_periodo_inteiro_nao_so_a_pagina(db):
    """Regressão: KPIs devem refletir o período INTEIRO, não a página (top-N por
    ROAS). Criativo de ROAS alto costuma ter baixo investimento — somar só a
    página subestima muito o investimento da carteira."""
    TS = db
    with TS() as s:
        admin = _admin(s)
        c = _cliente(s, slug="loja")
        # 1 criativo de ROAS altíssimo e investimento ínfimo (lidera o ranking)
        _criativo(s, cliente=c, rede=RedeAnuncio.META, ad_id="HI", nome="ROAS alto")
        _insight(s, cliente=c, rede=RedeAnuncio.META, ad_id="HI", dia=date(2026, 5, 1),
                 investimento=10, faturamento=5000, conversoes=1)
        # 3 criativos de ROAS baixo mas investimento alto (o grosso da verba)
        for i in range(3):
            _criativo(s, cliente=c, rede=RedeAnuncio.META, ad_id=f"LO{i}", nome=f"Volume {i}")
            _insight(s, cliente=c, rede=RedeAnuncio.META, ad_id=f"LO{i}", dia=date(2026, 5, 1),
                     investimento=1000, faturamento=1500, conversoes=20)
        s.commit()
        admin_id = admin.id

    with TS() as s:
        admin = s.get(Usuario, admin_id)
        # limit=1 → página traz só o ROAS alto (inv=10)
        items, total, totais = agregar_criativos(
            s, de=date(2026, 5, 1), ate=date(2026, 5, 31),
            rede="todos", categorias=None, gestor=None, cliente_slug=None,
            fat_min=None, fat_max=None, inv_min=None, inv_max=None,
            cli_fat_min=None, cli_fat_max=None, cli_inv_min=None, cli_inv_max=None,
            order_by="roas", limit=1, offset=0, user=admin,
        )
    soma_pagina = sum(it.investimento for it in items)
    assert total == 4
    assert soma_pagina == 10.0                       # a página (top-1 ROAS) é ínfima
    assert totais.criativos == 4
    assert totais.investimento == 3010.0             # 10 + 3*1000 = período INTEIRO
    assert totais.faturamento == 9500.0              # 5000 + 3*1500
    assert abs(totais.roas - (9500.0 / 3010.0)) < 1e-9

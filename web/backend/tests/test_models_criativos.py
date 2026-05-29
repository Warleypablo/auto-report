import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models import (
    AdInsight,
    Categoria,
    Cliente,
    Criativo,
    CriativoThumb,
    RedeAnuncio,
    ThumbStatus,
)
from models.base import Base

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _cliente(s, slug="c-criativos"):
    c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE)
    s.add(c)
    s.commit()
    s.refresh(c)
    return c


def test_cliente_gestor_travado_default_false(TS):
    with TS() as s:
        c = _cliente(s)
        assert c.gestor_travado is False


def test_criativo_cria_e_le(TS):
    with TS() as s:
        c = _cliente(s, slug="c-criativo-cria")
        cr = Criativo(
            cliente_id=c.id,
            rede=RedeAnuncio.META,
            ad_id="1203",
            nome="Criativo BF",
            tipo="video",
        )
        s.add(cr)
        s.commit()
        s.refresh(cr)
        assert isinstance(cr.id, uuid.UUID)
        assert cr.thumb_status is ThumbStatus.PENDENTE
        assert cr.nome == "Criativo BF"
        assert cr.primeiro_dia is None and cr.ultimo_dia is None


def test_criativo_unique_cliente_rede_ad(TS):
    with TS() as s:
        c = _cliente(s, slug="c-criativo-uniq")
        s.add(Criativo(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="999"))
        s.commit()
        s.add(Criativo(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="999"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_criativo_thumb_relationship_e_cascade(TS):
    with TS() as s:
        c = _cliente(s, slug="c-thumb")
        cr = Criativo(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="thumb-1")
        cr.thumb = CriativoThumb(conteudo=b"\x89PNG", mime="image/png")
        s.add(cr)
        s.commit()
        cr_id = cr.id
        assert cr.thumb is not None and cr.thumb.mime == "image/png"
        s.delete(cr)
        s.commit()
        assert s.get(CriativoThumb, cr_id) is None


def test_ad_insight_cria_com_defaults(TS):
    import datetime as dt
    from decimal import Decimal

    with TS() as s:
        c = _cliente(s, slug="c-insight")
        ins = AdInsight(
            cliente_id=c.id,
            rede=RedeAnuncio.META,
            ad_id="ad-1",
            dia=dt.date(2026, 5, 1),
        )
        s.add(ins)
        s.commit()
        s.refresh(ins)
        assert isinstance(ins.id, uuid.UUID)
        assert ins.investimento == Decimal("0")
        assert ins.faturamento == Decimal("0")
        assert ins.conversoes == Decimal("0")
        assert ins.impressoes == 0
        assert ins.clicks == 0
        assert ins.leads is None
        assert ins.video_3s is None
        assert ins.reach is None


def test_ad_insight_unique_cliente_rede_ad_dia(TS):
    import datetime as dt

    with TS() as s:
        c = _cliente(s, slug="c-insight-uniq")
        kwargs = dict(cliente_id=c.id, rede=RedeAnuncio.META, ad_id="x", dia=dt.date(2026, 5, 1))
        s.add(AdInsight(**kwargs))
        s.commit()
        s.add(AdInsight(**kwargs))
        with pytest.raises(IntegrityError):
            s.commit()


def test_ad_insight_reusa_enum_rede_anuncio(TS):
    # rede em criativos e ad_insights compartilham o MESMO tipo Postgres
    assert AdInsight.__table__.c.rede.type.name == "rede_anuncio"
    assert Criativo.__table__.c.rede.type.name == "rede_anuncio"

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from models import AdInsight, Categoria, Cliente, Criativo, RedeAnuncio, ThumbStatus
from models.base import Base

TEST_DB_URL = "postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine_test"


@pytest.fixture(scope="module")
def TS():
    engine = create_engine(TEST_DB_URL)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def cliente_id(TS):
    slug = f"test-criativos-{uuid.uuid4().hex[:8]}"
    with TS() as s:
        c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE, ativo=True)
        s.add(c)
        s.commit()
        cid = c.id
    yield cid
    with TS() as s:
        c = s.get(Cliente, cid)
        if c:
            s.delete(c)
            s.commit()


def test_upsert_ad_insight_insere_e_atualiza_sem_duplicar(TS, cliente_id):
    from etl.collect_criativos import upsert_ad_insight

    campos = dict(
        cliente_id=cliente_id,
        rede=RedeAnuncio.META,
        ad_id="ad-1",
        dia=date(2026, 5, 1),
        investimento=Decimal("10.00"),
        faturamento=Decimal("40.00"),
        conversoes=Decimal("2"),
        leads=None,
        impressoes=1000,
        clicks=10,
        video_3s=300,
        reach=800,
    )

    with TS() as s:
        upsert_ad_insight(s, **campos)
        s.commit()

    # mesmo (cliente, rede, ad_id, dia) com novos valores → UPDATE, não duplica
    campos2 = {**campos, "investimento": Decimal("99.00"), "faturamento": Decimal("123.00")}
    with TS() as s:
        upsert_ad_insight(s, **campos2)
        s.commit()

    with TS() as s:
        rows = s.scalars(
            select(AdInsight).where(
                AdInsight.cliente_id == cliente_id,
                AdInsight.ad_id == "ad-1",
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].investimento == Decimal("99.00")
        assert rows[0].faturamento == Decimal("123.00")
        assert rows[0].dia == date(2026, 5, 1)


def test_upsert_criativo_insere_metadados_e_expande_janela(TS, cliente_id):
    from etl.collect_criativos import upsert_criativo

    with TS() as s:
        upsert_criativo(
            s,
            cliente_id=cliente_id,
            rede=RedeAnuncio.META,
            ad_id="ad-9",
            nome="Criativo BF",
            tipo="video",
            preview_link="https://fb.com/preview/9",
            dia=date(2026, 5, 10),
        )
        s.commit()

    # dia anterior expande primeiro_dia; dia posterior expande ultimo_dia
    with TS() as s:
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-9",
            nome="Criativo BF", tipo="video",
            preview_link="https://fb.com/preview/9", dia=date(2026, 5, 5),
        )
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-9",
            nome="Criativo BF v2", tipo="video",
            preview_link="https://fb.com/preview/9", dia=date(2026, 5, 20),
        )
        s.commit()

    with TS() as s:
        rows = s.scalars(
            select(Criativo).where(
                Criativo.cliente_id == cliente_id, Criativo.ad_id == "ad-9"
            )
        ).all()
        assert len(rows) == 1
        cri = rows[0]
        assert cri.nome == "Criativo BF v2"      # metadado atualizado
        assert cri.tipo == "video"
        assert cri.preview_link == "https://fb.com/preview/9"
        assert cri.thumb_status == ThumbStatus.PENDENTE  # default no insert
        assert cri.primeiro_dia == date(2026, 5, 5)      # LEAST expandiu p/ trás
        assert cri.ultimo_dia == date(2026, 5, 20)       # GREATEST expandiu p/ frente


def test_upsert_criativo_preserva_thumb_status_existente(TS, cliente_id):
    from etl.collect_criativos import upsert_criativo

    with TS() as s:
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-7",
            nome="X", tipo="image", preview_link=None, dia=date(2026, 5, 1),
        )
        s.commit()
        cri = s.scalar(
            select(Criativo).where(
                Criativo.cliente_id == cliente_id, Criativo.ad_id == "ad-7"
            )
        )
        cri.thumb_status = ThumbStatus.OK
        s.commit()

    # re-upsert (novo dia) NÃO deve resetar thumb_status para PENDENTE
    with TS() as s:
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-7",
            nome="X2", tipo="image", preview_link=None, dia=date(2026, 5, 2),
        )
        s.commit()

    with TS() as s:
        cri = s.scalar(
            select(Criativo).where(
                Criativo.cliente_id == cliente_id, Criativo.ad_id == "ad-7"
            )
        )
        assert cri.thumb_status == ThumbStatus.OK
        assert cri.nome == "X2"


import httpx
import respx


@respx.mock
def test_meta_insights_diarios_parseia_linhas_por_dia():
    from etl.collect_criativos import _meta_insights_diarios

    payload = {
        "data": [
            {
                "ad_id": "ad-1", "ad_name": "Criativo A", "date_start": "2026-05-01",
                "spend": "10.50", "impressions": "1000", "clicks": "15", "reach": "800",
                "actions": [{"action_type": "omni_purchase", "value": "3"}],
                "action_values": [{"action_type": "omni_purchase", "value": "120.00"}],
                "video_3_sec_watched_actions": [{"value": "250"}],
            },
            {
                "ad_id": "ad-1", "ad_name": "Criativo A", "date_start": "2026-05-02",
                "spend": "5.00", "impressions": "400", "clicks": "4", "reach": "390",
                "actions": [], "action_values": [],
            },
        ]
    }
    respx.get(url__regex=r"https://graph\.facebook\.com/.*/insights").mock(
        return_value=httpx.Response(200, json=payload)
    )

    linhas = _meta_insights_diarios("act_999", date(2026, 5, 1), date(2026, 5, 2))

    assert len(linhas) == 2
    d1 = next(l for l in linhas if l["dia"] == date(2026, 5, 1))
    assert d1["ad_id"] == "ad-1"
    assert d1["ad_name"] == "Criativo A"
    assert d1["investimento"] == Decimal("10.50")
    assert d1["faturamento"] == Decimal("120.00")
    assert d1["conversoes"] == Decimal("3")
    assert d1["impressoes"] == 1000
    assert d1["clicks"] == 15
    assert d1["reach"] == 800
    assert d1["video_3s"] == 250

    d2 = next(l for l in linhas if l["dia"] == date(2026, 5, 2))
    assert d2["faturamento"] == Decimal("0")
    assert d2["conversoes"] == Decimal("0")
    assert d2["video_3s"] is None      # sem campo de vídeo → None


@respx.mock
def test_meta_metadados_lote_extrai_nome_tipo_thumb_e_link():
    from etl.collect_criativos import _meta_metadados_lote

    payload = {
        "ad-1": {
            "id": "ad-1",
            "name": "Criativo A",
            "preview_shareable_link": "https://fb.com/p/1",
            "creative": {
                "object_type": "VIDEO",
                "image_url": "https://cdn.fb.com/img1.jpg",
                "thumbnail_url": "https://cdn.fb.com/thumb1.jpg",
            },
        },
        "ad-2": {
            "id": "ad-2",
            "name": "Criativo B",
            "preview_shareable_link": "https://fb.com/p/2",
            "creative": {"object_type": "SHARE", "thumbnail_url": "https://cdn.fb.com/thumb2.jpg"},
        },
    }
    respx.get(url__regex=r"https://graph\.facebook\.com/v[\d.]+\?.*").mock(
        return_value=httpx.Response(200, json=payload)
    )

    meta = _meta_metadados_lote(["ad-1", "ad-2"])

    assert meta["ad-1"]["nome"] == "Criativo A"
    assert meta["ad-1"]["tipo"] == "video"                          # object_type lower
    assert meta["ad-1"]["preview_link"] == "https://fb.com/p/1"
    assert meta["ad-1"]["imagem_url"] == "https://cdn.fb.com/img1.jpg"    # image_url preferido
    assert meta["ad-2"]["imagem_url"] == "https://cdn.fb.com/thumb2.jpg"  # fallback thumbnail_url
    assert meta["ad-2"]["tipo"] == "share"


import io as _io

from PIL import Image as _Image

from models import CriativoThumb


def _png(w, h):
    buf = _io.BytesIO()
    _Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


@respx.mock
def test_coletar_criativos_meta_grava_insights_criativos_e_thumb(TS, cliente_id):
    from etl.collect_criativos import coletar_criativos_meta

    with TS() as s:
        c = s.get(Cliente, cliente_id)
        c.id_meta_ads = "act_777"
        s.commit()

    insights = {
        "data": [
            {
                "ad_id": "ad-1", "ad_name": "Criativo A", "date_start": "2026-05-01",
                "spend": "10.00", "impressions": "1000", "clicks": "15", "reach": "800",
                "actions": [{"action_type": "omni_purchase", "value": "3"}],
                "action_values": [{"action_type": "omni_purchase", "value": "120.00"}],
                "video_3_sec_watched_actions": [{"value": "250"}],
            }
        ]
    }
    metadados = {
        "ad-1": {
            "id": "ad-1", "name": "Criativo A",
            "preview_shareable_link": "https://fb.com/p/1",
            "creative": {"object_type": "VIDEO", "image_url": "https://cdn.fb.com/img1.jpg"},
        }
    }

    respx.get(url__regex=r"https://graph\.facebook\.com/.*/insights").mock(
        return_value=httpx.Response(200, json=insights)
    )
    respx.get(url__regex=r"https://graph\.facebook\.com/v[\d.]+\?.*").mock(
        return_value=httpx.Response(200, json=metadados)
    )
    respx.get("https://cdn.fb.com/img1.jpg").mock(
        return_value=httpx.Response(200, content=_png(640, 480),
                                    headers={"Content-Type": "image/png"})
    )

    with TS() as s:
        cliente = s.get(Cliente, cliente_id)
        ok = coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1),
                                    session_factory=TS)
    assert ok is True

    with TS() as s:
        ins = s.scalars(
            select(AdInsight).where(AdInsight.cliente_id == cliente_id)
        ).all()
        assert len(ins) == 1
        assert ins[0].investimento == Decimal("10.00")
        assert ins[0].faturamento == Decimal("120.00")

        cri = s.scalar(
            select(Criativo).where(Criativo.cliente_id == cliente_id)
        )
        assert cri.nome == "Criativo A"
        assert cri.tipo == "video"
        assert cri.preview_link == "https://fb.com/p/1"
        assert cri.thumb_status == ThumbStatus.OK

        thumb = s.get(CriativoThumb, cri.id)
        assert thumb is not None
        assert thumb.mime == "image/jpeg"
        img = _Image.open(_io.BytesIO(thumb.conteudo))
        assert max(img.size) == 320


@respx.mock
def test_coletar_criativos_meta_idempotente_em_rerun(TS, cliente_id):
    from etl.collect_criativos import coletar_criativos_meta

    with TS() as s:
        c = s.get(Cliente, cliente_id)
        c.id_meta_ads = "act_777"
        s.commit()

    insights = {
        "data": [
            {
                "ad_id": "ad-1", "ad_name": "Criativo A", "date_start": "2026-05-01",
                "spend": "10.00", "impressions": "1000", "clicks": "15", "reach": "800",
                "actions": [], "action_values": [],
            }
        ]
    }
    respx.get(url__regex=r"https://graph\.facebook\.com/.*/insights").mock(
        return_value=httpx.Response(200, json=insights)
    )
    respx.get(url__regex=r"https://graph\.facebook\.com/v[\d.]+\?.*").mock(
        return_value=httpx.Response(200, json={"ad-1": {"id": "ad-1", "name": "A",
            "creative": {"object_type": "SHARE"}}})  # sem imagem → SEM_IMAGEM
    )

    with TS() as s:
        cliente = s.get(Cliente, cliente_id)
        coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1), session_factory=TS)
    with TS() as s:
        cliente = s.get(Cliente, cliente_id)
        coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1), session_factory=TS)

    with TS() as s:
        ins = s.scalars(select(AdInsight).where(AdInsight.cliente_id == cliente_id)).all()
        cri = s.scalars(select(Criativo).where(Criativo.cliente_id == cliente_id)).all()
        assert len(ins) == 1     # rerun não duplica o fato
        assert len(cri) == 1     # rerun não duplica a dimensão
        assert cri[0].thumb_status == ThumbStatus.SEM_IMAGEM


def test_coletar_criativos_meta_sem_id_retorna_false(TS, cliente_id):
    from etl.collect_criativos import coletar_criativos_meta

    with TS() as s:
        cliente = s.get(Cliente, cliente_id)   # id_meta_ads = None
        ok = coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1),
                                    session_factory=TS)
    assert ok is False

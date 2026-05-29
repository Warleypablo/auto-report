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
            primeiro_dia=date(2026, 5, 10),
            ultimo_dia=date(2026, 5, 10),
        )
        s.commit()

    # dia anterior expande primeiro_dia; dia posterior expande ultimo_dia
    with TS() as s:
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-9",
            nome="Criativo BF", tipo="video",
            preview_link="https://fb.com/preview/9",
            primeiro_dia=date(2026, 5, 5), ultimo_dia=date(2026, 5, 5),
        )
        upsert_criativo(
            s, cliente_id=cliente_id, rede=RedeAnuncio.META, ad_id="ad-9",
            nome="Criativo BF v2", tipo="video",
            preview_link="https://fb.com/preview/9",
            primeiro_dia=date(2026, 5, 20), ultimo_dia=date(2026, 5, 20),
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
            nome="X", tipo="image", preview_link=None,
            primeiro_dia=date(2026, 5, 1), ultimo_dia=date(2026, 5, 1),
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
            nome="X2", tipo="image", preview_link=None,
            primeiro_dia=date(2026, 5, 2), ultimo_dia=date(2026, 5, 2),
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


@respx.mock
def test_coletar_criativos_meta_thumb_erro_nao_derruba_cliente(TS, cliente_id):
    from etl.collect_criativos import coletar_criativos_meta
    with TS() as s:
        c = s.get(Cliente, cliente_id); c.id_meta_ads = "act_777"; s.commit()
    insights = {"data": [{"ad_id": "ad-1", "ad_name": "A", "date_start": "2026-05-01",
        "spend": "10.00", "impressions": "100", "clicks": "2", "reach": "90",
        "actions": [], "action_values": []}]}
    meta = {"ad-1": {"id": "ad-1", "name": "A",
        "creative": {"object_type": "IMAGE", "image_url": "https://cdn.fb.com/bad.jpg"}}}
    respx.get(url__regex=r"https://graph\.facebook\.com/.*/insights").mock(
        return_value=httpx.Response(200, json=insights))
    respx.get(url__regex=r"https://graph\.facebook\.com/v[\d.]+\?.*").mock(
        return_value=httpx.Response(200, json=meta))
    respx.get("https://cdn.fb.com/bad.jpg").mock(return_value=httpx.Response(500))  # download falha
    with TS() as s:
        cliente = s.get(Cliente, cliente_id)
        ok = coletar_criativos_meta(cliente, date(2026, 5, 1), date(2026, 5, 1), session_factory=TS)
    assert ok is True
    with TS() as s:
        cri = s.scalar(select(Criativo).where(Criativo.cliente_id == cliente_id))
        assert cri.thumb_status == ThumbStatus.ERRO
        assert s.get(CriativoThumb, cri.id) is None
        assert len(s.scalars(select(AdInsight).where(AdInsight.cliente_id == cliente_id)).all()) == 1


@respx.mock
def test_meta_insights_diarios_pagina_seguindo_paging_next():
    """O loop while next_url deve agregar dados de todas as páginas."""
    from etl.collect_criativos import _meta_insights_diarios

    pagina2_url = "https://graph.facebook.com/v23.0/act_42/insights?after=cursor2"

    pagina1 = {
        "data": [
            {
                "ad_id": "ad-p1", "ad_name": "Pagina 1", "date_start": "2026-05-01",
                "spend": "5.00", "impressions": "500", "clicks": "5", "reach": "400",
                "actions": [], "action_values": [],
            }
        ],
        "paging": {"next": pagina2_url},
    }
    pagina2 = {
        "data": [
            {
                "ad_id": "ad-p2", "ad_name": "Pagina 2", "date_start": "2026-05-02",
                "spend": "7.00", "impressions": "700", "clicks": "7", "reach": "600",
                "actions": [], "action_values": [],
            }
        ]
        # sem "paging" → fim do loop
    }

    # Usa side_effect com contador para que a 1ª chamada retorne página 1
    # e a 2ª retorne página 2 — evita loop infinito se regex matchasse ambas.
    respostas = [
        httpx.Response(200, json=pagina1),
        httpx.Response(200, json=pagina2),
    ]
    call_count = 0

    def retorna_por_chamada(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        resp = respostas[call_count]
        call_count += 1
        return resp

    respx.get(url__regex=r"https://graph\.facebook\.com/.*insights.*").mock(
        side_effect=retorna_por_chamada
    )

    linhas = _meta_insights_diarios("42", date(2026, 5, 1), date(2026, 5, 2))

    assert call_count == 2, f"Esperado 2 chamadas HTTP (2 páginas), mas foram {call_count}"
    assert len(linhas) == 2, f"Esperado 2 linhas (2 páginas), recebido {len(linhas)}"
    ad_ids = {l["ad_id"] for l in linhas}
    assert "ad-p1" in ad_ids
    assert "ad-p2" in ad_ids


@respx.mock
def test_meta_insights_diarios_removeprefix_nao_corrompe_id_patologico():
    """removeprefix('act_') preserva id patológico 'caa_99' → URL act_caa_99/insights.
    lstrip('act_') corromperia para 'act_99' (strips chars 'a','c','t','_')."""
    from etl.collect_criativos import _meta_insights_diarios

    # id que NÃO começa com 'act_' mas cujos caracteres iniciais seriam consumidos por lstrip
    id_patologico = "caa_99"

    captured_urls: list[str] = []

    def captura_request(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(200, json={"data": []})

    respx.get(url__regex=r"https://graph\.facebook\.com/.*").mock(side_effect=captura_request)

    _meta_insights_diarios(id_patologico, date(2026, 5, 1), date(2026, 5, 1))

    assert len(captured_urls) == 1
    url_chamada = captured_urls[0]
    assert "act_caa_99/insights" in url_chamada, (
        f"URL esperada conter 'act_caa_99/insights', mas foi: {url_chamada}"
    )
    assert "act_99/insights" not in url_chamada, (
        f"URL corrompida por lstrip detectada: {url_chamada}"
    )


from unittest.mock import MagicMock, patch


def test_get_google_ads_service_usa_cred_manager():
    fake_client = MagicMock()
    fake_service = MagicMock()
    fake_client.get_service.return_value = fake_service
    with patch(
        "etl.collect_criativos._build_google_ads_client",
        return_value=fake_client,
    ):
        from etl.collect_criativos import _get_google_ads_service

        svc = _get_google_ads_service()

    assert svc is fake_service
    fake_client.get_service.assert_called_once_with("GoogleAdsService")


def test_build_google_query_contem_campos_e_datas():
    from datetime import date

    from etl.collect_criativos import _build_google_query

    q = _build_google_query(date(2026, 1, 1), date(2026, 1, 31))

    assert "FROM ad_group_ad" in q
    assert "segments.date BETWEEN '2026-01-01' AND '2026-01-31'" in q
    for campo in (
        "ad_group_ad.ad.id",
        "ad_group_ad.ad.name",
        "ad_group_ad.ad.type",
        "ad_group_ad.ad_group",
        "ad_group_ad.ad.image_ad.image_url",
        "segments.date",
        "metrics.cost_micros",
        "metrics.conversions",
        "metrics.conversions_value",
        "metrics.impressions",
        "metrics.clicks",
    ):
        assert campo in q


def test_google_deep_link():
    from etl.collect_criativos import _google_deep_link

    link = _google_deep_link(customer_id="1234567890", ad_group_id="555", ad_id="999")
    assert link == (
        "https://ads.google.com/aw/ads?ocid=1234567890&__e=999&adGroupId=555"
    )


def test_google_deep_link_sem_ad_group_retorna_none():
    from etl.collect_criativos import _google_deep_link

    assert _google_deep_link(customer_id="1234567890", ad_group_id=None, ad_id="999") is None
    assert _google_deep_link(customer_id="1234567890", ad_group_id="", ad_id="999") is None


def _fake_ad(type_name, *, image_url=""):
    ad = MagicMock()
    ad.type_.name = type_name
    ad.image_ad.image_url = image_url
    return ad


def test_google_thumb_url_image_ad():
    from etl.collect_criativos import _google_thumb_url

    ad = _fake_ad("IMAGE_AD", image_url="https://cdn.example/img.png")
    assert _google_thumb_url(ad) == "https://cdn.example/img.png"


def test_google_thumb_url_search_ad_retorna_none():
    from etl.collect_criativos import _google_thumb_url

    ad = _fake_ad("EXPANDED_TEXT_AD")
    assert _google_thumb_url(ad) is None


def test_google_thumb_url_image_ad_sem_url_retorna_none():
    from etl.collect_criativos import _google_thumb_url

    ad = _fake_ad("IMAGE_AD", image_url="")
    assert _google_thumb_url(ad) is None


def test_run_collect_criativos_ignora_cliente_ativo_sem_id_meta_ads(TS):
    """Cliente ativo mas com id_meta_ads=None NÃO deve ser processado.
    run_collect_criativos filtra via .isnot(None) na query."""
    from etl import collect_criativos as mod

    # Cria cliente ativo SEM id_meta_ads (slug único para não colidir)
    slug = f"test-sem-meta-{uuid.uuid4().hex[:8]}"
    with TS() as s:
        from models import Categoria
        c = Cliente(slug=slug, nome=slug, categoria=Categoria.ECOMMERCE, ativo=True)
        # id_meta_ads deixa None (default)
        s.add(c)
        s.commit()
        cliente_sem_meta_id = c.id

    try:
        chamados: list[uuid.UUID] = []

        def fake_coletar(cliente, since, until, session_factory=None):
            chamados.append(cliente.id)
            return True

        with patch.object(mod, "coletar_criativos_meta", side_effect=fake_coletar), \
             patch.object(mod, "SessionLocal", TS), \
             patch.object(mod, "advisory_lock") as fake_lock:
            fake_lock.return_value.__enter__ = lambda *a: None
            fake_lock.return_value.__exit__ = lambda *a: False
            resumo = mod.run_collect_criativos(backfill_meses=1)

        assert cliente_sem_meta_id not in chamados, (
            "coletar_criativos_meta foi chamado para cliente sem id_meta_ads"
        )
        # total reflete apenas clientes com id_meta_ads (este não entra na contagem)
        assert resumo["total"] == len(chamados)
    finally:
        with TS() as s:
            c = s.get(Cliente, cliente_sem_meta_id)
            if c:
                s.delete(c)
                s.commit()


def test_coletar_google_sem_id_retorna_true_sem_chamar_api():
    from etl.collect_criativos import coletar_criativos_google

    cliente = MagicMock()
    cliente.id_google_ads = None
    cliente.nome = "Sem Google"

    with patch("etl.collect_criativos._get_google_ads_service") as p:
        ok = coletar_criativos_google(cliente, date(2026, 1, 1), date(2026, 1, 31))

    assert ok is True
    p.assert_not_called()


def test_coletar_google_id_zero_retorna_true_sem_chamar_api():
    from etl.collect_criativos import coletar_criativos_google

    cliente = MagicMock()
    cliente.id_google_ads = "0"
    cliente.nome = "Google Off"

    with patch("etl.collect_criativos._get_google_ads_service") as p:
        ok = coletar_criativos_google(cliente, date(2026, 1, 1), date(2026, 1, 31))

    assert ok is True
    p.assert_not_called()


def test_run_collect_criativos_exige_exatamente_um_modo():
    from etl.collect_criativos import run_collect_criativos

    with pytest.raises(ValueError):
        run_collect_criativos()  # nenhum modo
    with pytest.raises(ValueError):
        run_collect_criativos(backfill_meses=6, incremental=True)  # ambos


def test_run_collect_criativos_backfill_chama_coletor_por_cliente(TS, cliente_id):
    from etl import collect_criativos as mod

    with TS() as s:
        c = s.get(Cliente, cliente_id)
        c.id_meta_ads = "act_777"
        s.commit()

    janelas = {}

    def fake_coletar(cliente, since, until, session_factory=None):
        janelas[cliente.id] = (since, until)
        return True

    with patch.object(mod, "coletar_criativos_meta", side_effect=fake_coletar), \
         patch.object(mod, "SessionLocal", TS), \
         patch.object(mod, "advisory_lock") as fake_lock:
        fake_lock.return_value.__enter__ = lambda *a: None
        fake_lock.return_value.__exit__ = lambda *a: False
        resumo = mod.run_collect_criativos(backfill_meses=6)

    assert resumo["ok"] >= 1
    assert resumo["total"] >= 1
    # janela de backfill ~6 meses (>= 150 dias)
    since, until = janelas[cliente_id]
    assert (until - since).days >= 150


def test_run_collect_criativos_incremental_usa_retroacao(TS, cliente_id):
    from datetime import date as _date, timedelta

    from etl import collect_criativos as mod

    with TS() as s:
        c = s.get(Cliente, cliente_id)
        c.id_meta_ads = "act_777"
        s.commit()

    janelas = {}

    def fake_coletar(cliente, since, until, session_factory=None):
        janelas[cliente.id] = (since, until)
        return True

    with patch.object(mod, "coletar_criativos_meta", side_effect=fake_coletar), \
         patch.object(mod, "SessionLocal", TS), \
         patch.object(mod, "advisory_lock") as fake_lock:
        fake_lock.return_value.__enter__ = lambda *a: None
        fake_lock.return_value.__exit__ = lambda *a: False
        mod.run_collect_criativos(incremental=True)

    since, until = janelas[cliente_id]
    ontem = _date.today() - timedelta(days=1)
    assert until == ontem
    assert since == ontem - timedelta(days=mod.RETROACAO_DIAS)

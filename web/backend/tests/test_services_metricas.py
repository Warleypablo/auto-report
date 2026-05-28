def test_build_timeline_imports():
    """Sanity: função existe e é importável.
    A cobertura comportamental real vem dos testes de endpoint
    (test_cliente_metricas), que rodam contra Postgres com snapshots semeados.
    """
    from services.metricas import build_timeline

    assert callable(build_timeline)


def test_build_breakdown_imports():
    from services.metricas import build_breakdown

    assert callable(build_breakdown)


def test_parse_br_handles_pt_format():
    """Parsers PT-BR continuam disponíveis a partir de services."""
    from services.metricas import _parse_br, _parse_int_br

    assert _parse_br("R$ 1.026,12") == 1026.12
    assert _parse_br("17,15") == 17.15
    assert _parse_br("-") is None
    assert _parse_br(None) is None
    assert _parse_int_br("1.234") == 1234
    assert _parse_int_br("-") is None


def test_meses_disponiveis_imports():
    from services.metricas import meses_disponiveis_for_cliente

    assert callable(meses_disponiveis_for_cliente)


def test_build_breakdown_parses_funil_metrics(monkeypatch):
    """build_breakdown deve parsear ctr/freq/hook (Meta) e ctr (Google) quando presentes,
    e devolver None quando ausentes."""
    from unittest.mock import MagicMock
    import services.metricas as svc

    # Snapshot fake com TODOS os placeholders novos no ad #1, e SEM os novos no ad #2.
    raw = {
        "{{nome_adf1}}": "Loop AI",
        "{{inv_adf1}}": "R$ 1.000,00",
        "{{lead_adf1}}": "10",
        "{{cpl_adf1}}": "R$ 100,00",
        "{{conv_adf1}}": "5",
        "{{fat_adf1}}": "R$ 5.000,00",
        "{{roas_adf1}}": "5,00",
        "{{cpa_adf1}}": "R$ 200,00",
        "{{imp_adf1}}": "1.000",
        "{{img_adf1}}": "https://example.com/a.jpg",
        "{{ctr_adf1}}": "2,40",
        "{{freq_adf1}}": "3,20",
        "{{hook_adf1}}": "38,00",
        "{{nome_adf2}}": "Brand B",
        "{{inv_adf2}}": "R$ 500,00",
        "{{imp_adf2}}": "500",
        "{{nome_adg1}}": "Search BR",
        "{{inv_adg1}}": "R$ 200,00",
        "{{ctr_adg1}}": "1,80",
    }

    snap = MagicMock()
    snap.raw_dados = raw
    snap.periodo_fim = None

    session = MagicMock()
    session.execute.return_value.scalars.return_value.first.return_value = snap

    out = svc.build_breakdown(MagicMock(), None, session)

    meta = out["meta_ads"]
    assert meta[0]["nome"] == "Loop AI"
    assert meta[0]["ctr"] == 2.40
    assert meta[0]["frequency"] == 3.20
    assert meta[0]["hook_rate"] == 38.00

    assert meta[1]["nome"] == "Brand B"
    assert meta[1]["ctr"] is None
    assert meta[1]["frequency"] is None
    assert meta[1]["hook_rate"] is None

    google = out["google_ads"]
    assert google[0]["nome"] == "Search BR"
    assert google[0]["ctr"] == 1.80

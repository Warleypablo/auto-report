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

def test_build_timeline_imports():
    """Sanity: função existe e é importável.
    A cobertura comportamental real vem dos testes de endpoint
    (test_cliente_metricas), que rodam contra Postgres com snapshots semeados.
    """
    from services.metricas import build_timeline

    assert callable(build_timeline)

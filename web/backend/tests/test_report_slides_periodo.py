from datetime import date

from services.report_slides import _resolver_periodo_ref


def test_semanal_com_semana_inicio():
    ref, comp = _resolver_periodo_ref("2026-06", "SEMANAL", "2026-06-08")
    assert (ref.inicio, ref.fim) == (date(2026, 6, 8), date(2026, 6, 12))
    # comparativo = semana anterior (seg 01 / sex 05)
    assert (comp.inicio, comp.fim) == (date(2026, 6, 1), date(2026, 6, 5))


def test_semanal_sem_semana_inicio_usa_vigente():
    ref, _comp = _resolver_periodo_ref("2026-06", "SEMANAL", None, today=date(2026, 6, 11))
    assert (ref.inicio, ref.fim) == (date(2026, 6, 8), date(2026, 6, 12))


def test_semanal_aceita_qualquer_dia_da_semana():
    # quinta 11/06 como semana_inicio ainda resolve seg 08 / sex 12
    ref, _ = _resolver_periodo_ref("2026-06", "SEMANAL", "2026-06-11")
    assert (ref.inicio, ref.fim) == (date(2026, 6, 8), date(2026, 6, 12))


def test_mensal_usa_mes_selecionado_e_ignora_semana_inicio():
    ref, comp = _resolver_periodo_ref("2026-05", "MENSAL", "2026-06-08")
    assert (ref.inicio, ref.fim) == (date(2026, 5, 1), date(2026, 5, 31))
    assert (comp.inicio, comp.fim) == (date(2026, 4, 1), date(2026, 4, 30))

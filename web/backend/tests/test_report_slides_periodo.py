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


def test_semanal_periodo_livre_usa_inicio_e_fim():
    # período livre de 10 dias: 10/06 a 19/06
    ref, comp = _resolver_periodo_ref(
        "2026-06", "SEMANAL", None, data_inicio="2026-06-10", data_fim="2026-06-19"
    )
    assert (ref.inicio, ref.fim) == (date(2026, 6, 10), date(2026, 6, 19))
    # comparativo = mesmos 10 dias imediatamente antes: 31/05 a 09/06
    assert (comp.inicio, comp.fim) == (date(2026, 5, 31), date(2026, 6, 9))


def test_semanal_periodo_livre_um_unico_dia():
    ref, comp = _resolver_periodo_ref(
        "2026-06", "SEMANAL", None, data_inicio="2026-06-10", data_fim="2026-06-10"
    )
    assert (ref.inicio, ref.fim) == (date(2026, 6, 10), date(2026, 6, 10))
    assert (comp.inicio, comp.fim) == (date(2026, 6, 9), date(2026, 6, 9))


def test_semanal_periodo_livre_tem_precedencia_sobre_semana_inicio():
    # se vierem ambos, o período livre (data_inicio/data_fim) vence
    ref, _ = _resolver_periodo_ref(
        "2026-06", "SEMANAL", "2026-06-01", data_inicio="2026-06-10", data_fim="2026-06-12"
    )
    assert (ref.inicio, ref.fim) == (date(2026, 6, 10), date(2026, 6, 12))


def test_semanal_periodo_livre_fim_plus_1():
    ref, _ = _resolver_periodo_ref(
        "2026-06", "SEMANAL", None, data_inicio="2026-06-10", data_fim="2026-06-19"
    )
    assert ref.fim_plus_1 == date(2026, 6, 20)

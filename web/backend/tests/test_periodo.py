from datetime import date

from core.periodo import Frequencia, periodo_referencia, semana_de, semana_vigente


def test_semana_de_segunda_a_sexta():
    # 2026-06-08 é segunda; 2026-06-12 é sexta
    p = semana_de(date(2026, 6, 8))
    assert p.inicio == date(2026, 6, 8)
    assert p.fim == date(2026, 6, 12)
    assert p.fim_plus_1 == date(2026, 6, 13)


def test_semana_de_qualquer_dia_cai_na_mesma_semana_util():
    # quarta, sexta, sábado e domingo da mesma semana → seg 08 / sex 12
    for d in (date(2026, 6, 10), date(2026, 6, 12), date(2026, 6, 13), date(2026, 6, 14)):
        p = semana_de(d)
        assert (p.inicio, p.fim) == (date(2026, 6, 8), date(2026, 6, 12))


def test_semana_vigente_usa_today():
    p = semana_vigente(today=date(2026, 6, 11))  # quinta
    assert (p.inicio, p.fim) == (date(2026, 6, 8), date(2026, 6, 12))


def test_periodo_referencia_semanal_usa_semana_vigente():
    p = periodo_referencia(today=date(2026, 6, 11), frequencia=Frequencia.SEMANAL)
    assert (p.inicio, p.fim) == (date(2026, 6, 8), date(2026, 6, 12))

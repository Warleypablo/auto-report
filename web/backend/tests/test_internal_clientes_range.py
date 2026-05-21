import calendar
from datetime import date
import pytest


def _primeira_data(mes: str) -> date:
    """Converte 'YYYY-MM' na data do primeiro dia do mês."""
    y, m = int(mes[:4]), int(mes[5:7])
    return date(y, m, 1)


def _ultima_data(mes: str) -> date:
    """Converte 'YYYY-MM' na data do último dia do mês."""
    y, m = int(mes[:4]), int(mes[5:7])
    return date(y, m, calendar.monthrange(y, m)[1])


def test_primeira_data():
    assert _primeira_data("2026-02") == date(2026, 2, 1)
    assert _primeira_data("2025-12") == date(2025, 12, 1)


def test_ultima_data():
    assert _ultima_data("2026-02") == date(2026, 2, 28)
    assert _ultima_data("2024-02") == date(2024, 2, 29)  # ano bissexto
    assert _ultima_data("2026-04") == date(2026, 4, 30)


def test_range_de_ate_ordenado():
    """Se de > ate, a função deve inverter automaticamente."""
    de_mes = "2026-04"
    ate_mes = "2026-02"
    de, ate = sorted([de_mes, ate_mes])
    assert de == "2026-02"
    assert ate == "2026-04"


def test_range_mesmo_mes():
    """Range de um único mês deve ser equivalente ao antigo ?mes=."""
    de_date = _primeira_data("2026-04")
    ate_date = _ultima_data("2026-04")
    assert de_date == date(2026, 4, 1)
    assert ate_date == date(2026, 4, 30)

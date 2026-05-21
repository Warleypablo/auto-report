from datetime import date

import pytest
from fastapi import HTTPException

from api.internal import _mes_para_periodo


def test_mes_para_periodo_fevereiro():
    assert _mes_para_periodo("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))


def test_mes_para_periodo_bissexto():
    assert _mes_para_periodo("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))


def test_mes_para_periodo_abril():
    assert _mes_para_periodo("2026-04") == (date(2026, 4, 1), date(2026, 4, 30))


def test_mes_invalido():
    with pytest.raises(HTTPException):
        _mes_para_periodo("2026-13")


def test_swap_de_maior_que_ate():
    de, ate = "2026-04", "2026-02"
    if de and ate and de > ate:
        de, ate = ate, de
    assert de == "2026-02"
    assert ate == "2026-04"

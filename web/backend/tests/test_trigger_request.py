"""Validação do TriggerRequest para o período livre do report semanal.

data_inicio/data_fim (YYYY-MM-DD) devem vir em par, com fim >= início e fim
não-futuro. Datas no passado garantido (mai/2026) para não depender do relógio.
"""
import pytest
from pydantic import ValidationError

from schemas.gestor import TriggerRequest


def test_trigger_aceita_periodo_livre_valido():
    req = TriggerRequest(
        slug="x", mes="2026-05", frequencia="SEMANAL",
        data_inicio="2026-05-01", data_fim="2026-05-10",
    )
    assert req.data_inicio == "2026-05-01"
    assert req.data_fim == "2026-05-10"


def test_trigger_rejeita_fim_antes_do_inicio():
    with pytest.raises(ValidationError):
        TriggerRequest(
            slug="x", mes="2026-05", frequencia="SEMANAL",
            data_inicio="2026-05-10", data_fim="2026-05-01",
        )


def test_trigger_rejeita_fim_no_futuro():
    with pytest.raises(ValidationError):
        TriggerRequest(
            slug="x", mes="2026-05", frequencia="SEMANAL",
            data_inicio="2026-05-01", data_fim="2099-01-01",
        )


def test_trigger_rejeita_data_incompleta():
    with pytest.raises(ValidationError):
        TriggerRequest(
            slug="x", mes="2026-05", frequencia="SEMANAL",
            data_inicio="2026-05-01",  # falta data_fim
        )


def test_trigger_sem_datas_continua_valido():
    req = TriggerRequest(
        slug="x", mes="2026-05", frequencia="SEMANAL", semana_inicio="2026-05-04",
    )
    assert req.data_inicio is None
    assert req.data_fim is None


def test_trigger_mensal_nao_exige_periodo():
    req = TriggerRequest(slug="x", mes="2026-05", frequencia="MENSAL")
    assert req.frequencia == "MENSAL"

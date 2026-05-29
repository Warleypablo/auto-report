"""Testa o fill gracioso (sem placeholders crus) do coletor ecommerce.

Cenários:
  1. Erro HTTP (ex.: range de datas futuro → 400 da Meta) → todos os ranks "-"
  2. Lista vazia devolvida pela API → todos os ranks "-"
"""
from __future__ import annotations

import types
from datetime import date
from unittest.mock import MagicMock, patch

import requests

import core.categorias.ecommerce.campaign_facebook_gather as mod


_CLIENTE = types.SimpleNamespace(nome="Teste", id_meta_ads="123456789")
_PERIODO = types.SimpleNamespace(inicio=date(2026, 6, 8), fim=date(2026, 6, 14))
_TOP_N   = 20


def _mock_set_status(cliente, status):  # noqa: ANN001
    """Substituto inerte de set_status para não precisar de DB."""


def test_http_error_retorna_placeholders_vazios():
    """Quando a API devolve HTTP 400/4xx, o retorno deve ter todos os ranks."""
    resp_mock = MagicMock()
    resp_mock.text = "since cannot be in the future"
    http_err = requests.HTTPError(response=resp_mock)

    requests_mock = MagicMock()
    get_mock = MagicMock()
    get_mock.raise_for_status.side_effect = http_err
    requests_mock.get.return_value = get_mock
    requests_mock.HTTPError = requests.HTTPError

    with patch.object(mod, "requests", requests_mock), \
         patch.object(mod, "set_status", _mock_set_status):
        out = mod.coletar_metricas_anuncios_meta(_CLIENTE, _PERIODO, top_n=_TOP_N)

    assert out, "retorno não deve ser vazio ({})"
    assert out["{{nome_adf1}}"] == "-", f"esperado '-', obtido {out['{{nome_adf1}}']!r}"
    assert "{{nome_adf20}}" in out, "rank 20 deve estar presente"
    assert out["{{img_adf1}}"] == "__NO_IMAGE__"


def test_lista_vazia_retorna_placeholders_vazios():
    """Quando a API devolve data:[], o retorno deve ter todos os ranks."""
    resp_mock = MagicMock()
    resp_mock.raise_for_status.return_value = None
    resp_mock.json.return_value = {"data": []}

    requests_mock = MagicMock()
    requests_mock.get.return_value = resp_mock
    requests_mock.HTTPError = requests.HTTPError

    with patch.object(mod, "requests", requests_mock), \
         patch.object(mod, "set_status", _mock_set_status):
        out = mod.coletar_metricas_anuncios_meta(_CLIENTE, _PERIODO, top_n=_TOP_N)

    assert out["{{nome_adf1}}"] == "-"
    assert out["{{nome_adf5}}"] == "-"
    assert out["{{img_adf3}}"] == "__NO_IMAGE__"

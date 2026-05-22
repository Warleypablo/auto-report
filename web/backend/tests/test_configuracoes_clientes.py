"""Testes para os schemas de edição e detalhe de clientes."""
import uuid
import pytest


def test_cliente_edit_request_partial():
    """Só os campos enviados devem ficar em model_fields_set."""
    from schemas.gestor import ClienteEditRequest
    req = ClienteEditRequest(nome="Novo Nome", gestor="Ana")
    data = req.model_dump(exclude_unset=True)
    assert data == {"nome": "Novo Nome", "gestor": "Ana"}
    assert "id_google_ads" not in data


def test_cliente_edit_request_null_clears_field():
    """Campo explicitamente null deve ser incluído (para limpar o valor)."""
    from schemas.gestor import ClienteEditRequest
    req = ClienteEditRequest(gestor=None)
    data = req.model_dump(exclude_unset=True)
    assert "gestor" in data
    assert data["gestor"] is None


def test_cliente_edit_request_categoria_valida():
    from schemas.gestor import ClienteEditRequest
    req = ClienteEditRequest(categoria="E-commerce")
    assert req.categoria == "E-commerce"


def test_cliente_edit_request_categoria_invalida():
    from schemas.gestor import ClienteEditRequest
    with pytest.raises(Exception):
        ClienteEditRequest(categoria="Invalida")


def test_cliente_detalhe_item_fields():
    """ClienteDetalheItem deve ter todos os campos esperados."""
    from schemas.gestor import ClienteDetalheItem
    item = ClienteDetalheItem(
        id=uuid.uuid4(),
        slug="meu-cliente",
        nome="Meu Cliente",
        categoria="E-commerce",
        gestor="Ana",
        id_google_ads="123",
        id_meta_ads="456",
        id_ga4="G-789",
        painel_url="https://example.com/painel",
        pasta_url="https://example.com/pasta",
        ativo=True,
    )
    assert item.slug == "meu-cliente"
    assert item.ativo is True


def test_cliente_detalhe_item_nullable_fields():
    """Campos opcionais devem aceitar None."""
    from schemas.gestor import ClienteDetalheItem
    item = ClienteDetalheItem(
        id=uuid.uuid4(),
        slug="slug",
        nome="Nome",
        categoria="Lead Com Site",
        ativo=True,
    )
    assert item.gestor is None
    assert item.id_google_ads is None

from etl.cliente_publico import ClientePublico, slugify


class FakeCoreCliente:
    def __init__(self, nome, categoria, extras=None):
        self.nome = nome
        self.categoria = categoria
        self.extras = extras or {}


def test_slugify_remove_acentos():
    assert slugify("Loja Fashion BR") == "loja-fashion-br"
    assert slugify("Dental Care+") == "dental-care"
    assert slugify("Açaí & Cia.") == "acai-cia"


def test_publicar_vitrine_true(monkeypatch):
    c = FakeCoreCliente("Acme", "E-commerce", {"PUBLICAR_VITRINE": "TRUE"})
    p = ClientePublico.from_cliente(c)
    assert p.publicar_vitrine is True
    assert p.slug == "acme"
    assert p.nome == "Acme"


def test_publicar_vitrine_false_quando_ausente():
    c = FakeCoreCliente("Acme", "E-commerce", {})
    p = ClientePublico.from_cliente(c)
    assert p.publicar_vitrine is False


def test_publicar_vitrine_aceita_sim_x_1():
    for val in ("SIM", "x", "1", "Verdadeiro"):
        c = FakeCoreCliente("X", "E-commerce", {"PUBLICAR_VITRINE": val})
        assert ClientePublico.from_cliente(c).publicar_vitrine is True


def test_le_campos_publicos_de_extras():
    c = FakeCoreCliente("Loja", "E-commerce", {
        "PUBLICAR_VITRINE": "TRUE",
        "LOGO_URL": "/logos/loja.svg",
        "DESCRICAO_PUBLICA": "Caso da loja.",
        "SETOR_PUBLICO": "Moda",
        "PORTE_PUBLICO": "Médio",
    })
    p = ClientePublico.from_cliente(c)
    assert p.logo_url == "/logos/loja.svg"
    assert p.descricao_publica == "Caso da loja."
    assert p.setor == "Moda"
    assert p.porte == "Médio"


def test_string_vazia_vira_none():
    c = FakeCoreCliente("X", "E-commerce", {"LOGO_URL": "   "})
    assert ClientePublico.from_cliente(c).logo_url is None


def test_preserva_cliente_core():
    c = FakeCoreCliente("Acme", "E-commerce")
    p = ClientePublico.from_cliente(c)
    assert p.cliente_core is c

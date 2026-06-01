import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch


class TestNormalizarDados:
    def test_strip_double_braces(self):
        from core.pdf_generator import normalizar_dados
        dados = {"{{fat_sem}}": "R$ 100,00", "{{roas}}": "4,2"}
        assert normalizar_dados(dados) == {"fat_sem": "R$ 100,00", "roas": "4,2"}

    def test_chave_sem_braces_passa_intacta(self):
        from core.pdf_generator import normalizar_dados
        assert normalizar_dados({"fat_sem": "R$ 100,00"}) == {"fat_sem": "R$ 100,00"}

    def test_dict_vazio(self):
        from core.pdf_generator import normalizar_dados
        assert normalizar_dados({}) == {}

    def test_sufixo_comp_preservado(self):
        from core.pdf_generator import normalizar_dados
        dados = {"{{fat_sem_comp}}": "R$ 80,00"}
        assert normalizar_dados(dados) == {"fat_sem_comp": "R$ 80,00"}


class TestSelecionarTemplate:
    def test_ecommerce(self):
        from core.pdf_generator import selecionar_template
        assert selecionar_template("E-commerce") == "ecommerce.html"

    def test_lead_com_site(self):
        from core.pdf_generator import selecionar_template
        assert selecionar_template("Lead Com Site") == "lead_com_site.html"

    def test_lead_sem_site(self):
        from core.pdf_generator import selecionar_template
        assert selecionar_template("Lead Sem Site") == "lead_sem_site.html"

    def test_categoria_invalida_levanta_value_error(self):
        from core.pdf_generator import selecionar_template
        with pytest.raises(ValueError, match="Categoria sem template PDF"):
            selecionar_template("Inexistente")


class TestNormalizarDeltaClasse:
    def test_valor_positivo_retorna_up(self):
        from core.pdf_generator import delta_class
        assert delta_class("+23%") == "up"
        assert delta_class("↑ +5,2%") == "up"

    def test_valor_negativo_retorna_down(self):
        from core.pdf_generator import delta_class
        assert delta_class("-10%") == "down"
        assert delta_class("↓ -3,1%") == "down"

    def test_dash_retorna_neutro(self):
        from core.pdf_generator import delta_class
        assert delta_class("—") == "neutral"
        assert delta_class("") == "neutral"


class TestSalvarPdf:
    def test_cria_arquivo_no_caminho_correto(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from core.pdf_generator import salvar_pdf
        pdf_bytes = b"%PDF-1.4 fake content"
        caminho = salvar_pdf(pdf_bytes, "Acme Store", 2026, 5, 22)
        assert caminho.exists()
        assert caminho.read_bytes() == pdf_bytes
        assert "Acme_Store" in str(caminho)
        assert "2026/05" in str(caminho)

    def test_nome_com_caracteres_especiais_sanitizado(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from core.pdf_generator import salvar_pdf
        caminho = salvar_pdf(b"x", "Cliente & Cia.", 2026, 5, 22)
        assert "&" not in str(caminho)
        assert "." not in caminho.stem


class TestHtmlParaPdfSmoke:
    def test_retorna_bytes_pdf(self):
        from core.pdf_generator import html_para_pdf
        html = "<!DOCTYPE html><html><body><p>OK</p></body></html>"
        pdf = html_para_pdf(html)
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"

    def test_pdf_abaixo_de_4mb(self):
        from core.pdf_generator import html_para_pdf
        html = "<!DOCTYPE html><html><body>" + "<p>Linha de conteúdo</p>" * 100 + "</body></html>"
        pdf = html_para_pdf(html)
        assert len(pdf) < 4 * 1024 * 1024

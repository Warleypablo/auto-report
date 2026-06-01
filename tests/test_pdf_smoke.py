"""
Smoke test end-to-end: dados mock → HTML → PDF real.
Requer Playwright instalado (playwright install chromium).
Lento (~15-30s total) — rodar com: python3 -m pytest tests/test_pdf_smoke.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.pdf_generator import gerar_pdf, salvar_pdf

_DADOS_ECOMMERCE = {
    "{{cliente}}":             "Acme Store (Teste)",
    "{{periodo_inicio}}":      "26/05/2026",
    "{{periodo_fim}}":         "30/05/2026",
    "{{periodo_inicio_comp}}": "19/05/2026",
    "{{periodo_fim_comp}}":    "23/05/2026",
    "{{semana}}":              "22",
    "{{freq}}":                "Semana",
    "{{fat_sem}}":             "R$ 847.320,00",
    "{{fat_sem_comp}}":        "R$ 686.700,00",
    "{{var_fat_sem}}":         "+23,4%",
    "{{roas}}":                "8,4x",
    "{{roas_comp}}":           "7,2x",
    "{{var_roas}}":            "+1,2",
    "{{inv_sem}}":             "R$ 72.900,00",
    "{{var_inv_sem}}":         "+8%",
    "{{vendas}}":              "3.840",
    "{{var_vendas}}":          "+24%",
    "{{fat_bruto}}":           "R$ 1.210.000,00",
    "{{var_fat_bruto}}":       "+31%",
    "{{pedidos}}":             "3.840",
    "{{var_pedidos}}":         "+24%",
    "{{tck_med}}":             "R$ 315,00",
    "{{sessoes}}":             "68.420",
    "{{var_sessoes}}":         "+18%",
    "{{taxa_conv}}":           "2,8%",
    "{{var_taxa_conv}}":       "+0,3",
    "{{proximo_report}}":      "Semana 23 · 02/06/2026",
}


def test_pdf_ecommerce_valido():
    pdf = gerar_pdf("E-commerce", _DADOS_ECOMMERCE)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF", "Bytes não correspondem a PDF válido"


def test_pdf_ecommerce_abaixo_4mb():
    pdf = gerar_pdf("E-commerce", _DADOS_ECOMMERCE)
    tamanho_mb = len(pdf) / (1024 * 1024)
    assert tamanho_mb < 4.0, f"PDF muito grande para WhatsApp: {tamanho_mb:.2f} MB"


def test_pdf_salvo_em_disco(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf = gerar_pdf("E-commerce", _DADOS_ECOMMERCE)
    caminho = salvar_pdf(pdf, "Acme Store (Teste)", 2026, 5, 22)
    assert caminho.exists()
    assert caminho.stat().st_size > 0
    assert "Acme_Store" in str(caminho)


_DADOS_LEAD = {
    "{{cliente}}":             "Lead Teste",
    "{{periodo_inicio}}":      "26/05/2026",
    "{{periodo_fim}}":         "30/05/2026",
    "{{periodo_inicio_comp}}": "19/05/2026",
    "{{periodo_fim_comp}}":    "23/05/2026",
    "{{semana}}":              "22",
    "{{freq}}":                "Semana",
    "{{leads}}":               "1.284",
    "{{var_leads}}":           "+12%",
    "{{cpl}}":                 "R$ 12,80",
    "{{inv_sem}}":             "R$ 16.435,20",
    "{{var_inv_sem}}":         "+5%",
    "{{proximo_report}}":      "Semana 23 · 02/06/2026",
}


def test_pdf_lead_com_site_valido():
    pdf = gerar_pdf("Lead Com Site", _DADOS_LEAD)
    assert pdf[:4] == b"%PDF"


def test_pdf_lead_sem_site_valido():
    pdf = gerar_pdf("Lead Sem Site", _DADOS_LEAD)
    assert pdf[:4] == b"%PDF"

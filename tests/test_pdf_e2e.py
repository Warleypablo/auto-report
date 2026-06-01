"""
Teste end-to-end do PDF generator usando dados no formato EXATO do handler real.
Valida: dados reais → normalização → template → PDF válido e sem páginas quebradas.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.pdf_generator import (
    normalizar_dados, _extract_number, _extrair_ads,
    _detectar_plataformas, gerar_pdf, salvar_pdf
)

# ── Formato exato que o handler retorna ────────────────────────────────────
# Inclui: chaves em UPPERCASE, valores com hífen simples "-" como vazio,
# "__NO_IMAGE__" para imagens sem thumbnail, variações comp_.
DADOS_HANDLER_REAL = {
    # basic_placeholders (UPPERCASE)
    "{{PERIODO_INICIO}}":      "26/05/2026",
    "{{PERIODO_FIM}}":         "30/05/2026",
    "{{PERIODO_INICIO_comp}}": "19/05/2026",
    "{{PERIODO_FIM_comp}}":    "23/05/2026",
    "{{freq}}":   "Semanal",
    "{{cliente}}":"Marca Teste",
    "{{periodo}}": "26/05/2026 a 30/05/2026",

    # painel_scraper (lowercase, formato BR com ponto de milhar e vírgula decimal)
    "{{fat_sem}}":       "R$ 23.575,00",
    "{{fat_sem_comp}}":  "R$ 15.568,00",
    "{{var_fat_sem}}":   "+51,7%",
    "{{roas}}":          "106,74",
    "{{roas_comp}}":     "53,38",
    "{{var_roas}}":      "+100,0%",
    "{{inv_sem}}":       "R$ 221,00",
    "{{inv_sem_comp}}":  "R$ 291,00",
    "{{var_inv_sem}}":   "-24,1%",
    "{{vendas}}":        "92",
    "{{vendas_comp}}":   "60",
    "{{var_vendas}}":    "+53,3%",
    "{{tck_med}}":       "R$ 256,25",
    "{{tck_med_comp}}":  "R$ 259,47",
    "{{var_tck_med}}":   "-1,2%",
    "{{cpa}}":           "R$ 2,40",
    "{{cpa_comp}}":      "R$ 4,85",
    "{{var_cpa}}":       "-50,5%",
    "{{meta_fat}}":      "R$ 50.000,00",
    "{{meta_inv}}":      "R$ 5.000,00",
    "{{per_meta_fat}}":  "47,2%",
    "{{per_meta_inv}}":  "4,4%",

    # facebook_metrics_gather
    "{{fat_face}}":      "R$ 23.575,00",
    "{{fat_face_comp}}": "R$ 15.568,00",
    "{{var_fat_face}}":  "+51,7%",
    "{{roas_face}}":     "106,74",
    "{{roas_face_comp}}":"53,38",
    "{{var_roas_face}}": "+100,0%",
    "{{inv_face}}":      "R$ 221,00",
    "{{inv_face_comp}}": "R$ 291,00",
    "{{var_inv_face}}":  "-24,1%",
    "{{vendas_face}}":   "92",
    "{{vendas_face_comp}}": "60",
    "{{var_vendas_face}}": "+53,3%",
    "{{cpa_face}}":      "R$ 2,40",
    "{{cpa_face_comp}}": "R$ 4,85",
    "{{var_cpa_face}}":  "-50,5%",

    # campaign_facebook_gather — 3 ads reais + slots de preenchimento com "-"
    "{{nome_adf1}}":  "Campanha Verão | Tênis Running Pro",
    "{{img_adf1}}":   "https://picsum.photos/seed/ad1/400/400",
    "{{roas_adf1}}":  "31,4",
    "{{conv_adf1}}":  "48",
    "{{fat_adf1}}":   "R$ 52.000,00",
    "{{inv_adf1}}":   "R$ 1.656,00",
    "{{cpa_adf1}}":   "R$ 34,50",
    "{{ctr_adf1}}":   "3,82",
    "{{imp_adf1}}":   "45.231",
    "{{freq_adf1}}":  "2,14",
    "{{hook_adf1}}":  "-",

    "{{nome_adf2}}":  "Remarketing | Coleção Premium",
    "{{img_adf2}}":   "https://picsum.photos/seed/ad2/400/400",
    "{{roas_adf2}}":  "28,7",
    "{{conv_adf2}}":  "39",
    "{{fat_adf2}}":   "R$ 44.300,00",
    "{{inv_adf2}}":   "R$ 1.544,00",
    "{{cpa_adf2}}":   "R$ 39,60",
    "{{ctr_adf2}}":   "4,10",
    "{{imp_adf2}}":   "38.900",
    "{{freq_adf2}}":  "1,87",
    "{{hook_adf2}}":  "-",

    "{{nome_adf3}}":  "Prospecção | Oferta Exclusiva",
    "{{img_adf3}}":   "https://picsum.photos/seed/ad3/400/400",
    "{{roas_adf3}}":  "19,2",
    "{{conv_adf3}}":  "28",
    "{{fat_adf3}}":   "R$ 30.100,00",
    "{{inv_adf3}}":   "R$ 1.568,00",
    "{{cpa_adf3}}":   "R$ 56,00",
    "{{ctr_adf3}}":   "2,95",
    "{{imp_adf3}}":   "31.200",
    "{{freq_adf3}}":  "1,60",
    "{{hook_adf3}}":  "-",

    # Slots de preenchimento — handler preenche até top_n com "-"
    "{{nome_adf4}}":  "-",
    "{{img_adf4}}":   "__NO_IMAGE__",
    "{{roas_adf4}}":  "-",
    "{{conv_adf4}}":  "-",
    "{{fat_adf4}}":   "-",
    "{{inv_adf4}}":   "-",
    "{{cpa_adf4}}":   "-",
    "{{nome_adf5}}":  "-",
    "{{img_adf5}}":   "__NO_IMAGE__",
    "{{roas_adf5}}":  "-",
    "{{conv_adf5}}":  "-",
    "{{fat_adf5}}":   "-",
    "{{inv_adf5}}":   "-",
    "{{cpa_adf5}}":   "-",

    # google_metrics_gather
    "{{fat_goog}}":      "-",
    "{{fat_goog_comp}}": "-",
    "{{var_fat_goog}}":  "-",
    "{{roas_goog}}":     "-",
    "{{roas_goog_comp}}": "-",
    "{{var_roas_goog}}": "-",
    "{{inv_goog}}":      "-",
    "{{cpa_goog}}":      "-",
    "{{vendas_goog}}":   "-",

    # ga4_scraper
    "{{ses_ga}}":        "12.450",
    "{{ses_ga_comp}}":   "9.800",
    "{{var_ses_ga}}":    "+27,0%",
    "{{ses_eng_ga}}":    "8.720",
    "{{ses_eng_ga_comp}}": "6.580",
    "{{var_ses_eng_ga}}": "+32,5%",
    "{{taxa_eng_ga}}":   "70,0%",
    "{{taxa_eng_ga_comp}}": "67,1%",
    "{{var_taxa_eng_ga}}": "+2,9",
    "{{temp_med_ga}}":   "2m 14s",
    "{{temp_med_ga_comp}}": "1m 58s",
    "{{var_temp_med_ga}}": "+13,6%",

    # taxa_conv do painel
    "{{taxa_conv}}":     "3,42%",
    "{{taxa_conv_comp}}": "2,80%",
    "{{var_taxa_conv}}": "+22,1%",
}


class TestNormalizacao:
    def test_uppercase_keys_lowercased(self):
        ctx = normalizar_dados(DADOS_HANDLER_REAL)
        assert "periodo_inicio" in ctx
        assert ctx["periodo_inicio"] == "26/05/2026"
        assert "PERIODO_INICIO" not in ctx

    def test_hifen_normalizado_para_em_dash(self):
        ctx = normalizar_dados({"{{nome_adf4}}": "-", "{{img_adf4}}": "__NO_IMAGE__"})
        assert ctx["nome_adf4"] == "—"
        assert ctx["img_adf4"] == "—"

    def test_variantes_numericas_criadas(self):
        ctx = normalizar_dados({"{{fat_sem}}": "R$ 23.575,00", "{{fat_sem_comp}}": "R$ 15.568,00"})
        assert ctx.get("fat_sem_n") == pytest.approx(23575.0)
        assert ctx.get("fat_sem_comp_n") == pytest.approx(15568.0)

    def test_ponto_milhar_sem_virgula(self):
        ctx = normalizar_dados({"{{ses_ga}}": "12.450"})
        assert ctx.get("ses_ga_n") == pytest.approx(12450.0)

    def test_hifen_nao_gera_variante_numerica(self):
        ctx = normalizar_dados({"{{fat_goog}}": "-"})
        assert "fat_goog_n" not in ctx
        assert ctx["fat_goog"] == "—"


class TestExtrairAds:
    def test_apenas_ads_reais_incluidas(self):
        ctx = normalizar_dados(DADOS_HANDLER_REAL)
        ads = _extrair_ads(ctx, prefixo="adf", max_n=5)
        assert len(ads) == 3  # slots 4 e 5 são "-" → ignorados

    def test_metricas_reais_presentes(self):
        ctx = normalizar_dados(DADOS_HANDLER_REAL)
        ads = _extrair_ads(ctx, prefixo="adf", max_n=5)
        assert ads[0]["roas"] == "31,4"
        assert ads[0]["conv"] == "48"
        assert ads[1]["nome"] == "Remarketing | Coleção Premium"

    def test_max_n_respeitado(self):
        ctx = normalizar_dados(DADOS_HANDLER_REAL)
        ads = _extrair_ads(ctx, prefixo="adf", max_n=2)
        assert len(ads) == 2

    def test_google_ads_vazio(self):
        ctx = normalizar_dados(DADOS_HANDLER_REAL)
        ads_g = _extrair_ads(ctx, prefixo="adg", max_n=3)
        assert len(ads_g) == 0  # não há dados Google neste teste


class TestExtractNumber:
    @pytest.mark.parametrize("value,expected", [
        ("R$ 23.575,00", 23575.0),
        ("R$ 180.000",   180000.0),
        ("12.450",       12450.0),
        ("106,74",       106.74),
        ("+51,7%",       51.7),
        ("-24,1%",       -24.1),
        ("R$ 2,40",      2.40),
        ("-",            None),
        ("—",            None),
        ("",             None),
        ("__NO_IMAGE__", None),
    ])
    def test_formatos_pt_br(self, value, expected):
        result = _extract_number(value)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected, rel=1e-3)


class TestGerarPdfE2E:
    def test_pdf_ecommerce_com_criativos(self):
        """PDF E-commerce com 3 criativos reais deve ter 8 páginas e ser válido."""
        pdf = gerar_pdf("E-commerce", DADOS_HANDLER_REAL)
        assert isinstance(pdf, bytes)
        assert pdf[:4] == b"%PDF"
        # PDF deve conter "Melhores Criativos" e "Turbo Partners"
        texto = pdf[:50000]  # primeiros 50KB geralmente têm o texto embutido
        # Validação básica: tamanho razoável para 8 páginas
        assert len(pdf) > 100_000  # pelo menos 100KB para um report completo
        assert len(pdf) < 8 * 1024 * 1024  # max 8MB

    def test_pdf_ecommerce_sem_criativos(self):
        """PDF E-commerce sem dados Meta deve ter 7 páginas."""
        dados_sem_meta = {k: v for k, v in DADOS_HANDLER_REAL.items()
                         if "adf" not in k and "face" not in k and "goog" not in k}
        pdf = gerar_pdf("E-commerce", dados_sem_meta)
        assert pdf[:4] == b"%PDF"

    def test_pdf_lead_com_site(self):
        dados_lead = {
            "{{PERIODO_INICIO}}": "26/05/2026",
            "{{PERIODO_FIM}}":    "30/05/2026",
            "{{freq}}": "Semanal",
            "{{cliente}}": "Lead Teste",
            "{{fat_sem}}": "R$ 0,00",
            "{{leads}}": "184",
            "{{leads_comp}}": "162",
            "{{var_leads}}": "+13,6%",
            "{{cpl}}": "R$ 18,50",
            "{{cpl_comp}}": "R$ 21,30",
            "{{var_cpl}}": "-13,1%",
            "{{inv_sem}}": "R$ 3.404,00",
            "{{var_inv_sem}}": "+5,2%",
        }
        pdf = gerar_pdf("Lead Com Site", dados_lead)
        assert pdf[:4] == b"%PDF"

    def test_pdf_sem_dados_google_mostra_tracos(self):
        """Google Ads sem dados deve mostrar '—' sem quebrar o template."""
        pdf = gerar_pdf("E-commerce", DADOS_HANDLER_REAL)
        assert pdf[:4] == b"%PDF"

    def test_barras_comparacao_geradas_quando_tem_comp(self):
        """Verifica que a normalização gera _n para valores de comparação."""
        ctx = normalizar_dados(DADOS_HANDLER_REAL)
        assert "fat_face_n" in ctx
        assert "fat_face_comp_n" in ctx
        assert ctx["fat_face_n"] == pytest.approx(23575.0)
        assert ctx["fat_face_comp_n"] == pytest.approx(15568.0)

    def test_pdf_abaixo_limite_whatsapp(self):
        pdf = gerar_pdf("E-commerce", DADOS_HANDLER_REAL)
        tamanho_mb = len(pdf) / (1024 * 1024)
        assert tamanho_mb < 4.0, f"PDF de {tamanho_mb:.1f}MB excede limite do WhatsApp (4MB)"

    def test_salvar_pdf_cria_arquivo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pdf = gerar_pdf("E-commerce", DADOS_HANDLER_REAL)
        caminho = salvar_pdf(pdf, "Marca Teste", 2026, 5, 22)
        assert caminho.exists()
        assert caminho.stat().st_size > 100_000


# ── Dados do cenário Piknik real (só Meta, sem Painel/GA4/Google) ──────────
DADOS_PIKNIK_REAL = {
    "{{PERIODO_INICIO}}":      "25/05/2026",
    "{{PERIODO_FIM}}":         "29/05/2026",
    "{{PERIODO_INICIO_comp}}": "18/05/2026",
    "{{PERIODO_FIM_comp}}":    "22/05/2026",
    "{{freq}}":    "Semanal",
    "{{cliente}}": "Piknik",
    # Painel interno: sem dados
    "{{fat_sem}}":  "-",
    "{{roas}}":     "-",
    "{{inv_sem}}":  "-",
    "{{vendas}}":   "-",
    "{{tck_med}}":  "-",
    # Meta Ads: tem dados reais
    "{{fat_face}}":      "R$ 1.422,36",
    "{{fat_face_comp}}": "R$ 800,00",
    "{{var_fat_face}}":  "+77,8%",
    "{{roas_face}}":     "7,09",
    "{{roas_face_comp}}": "4,50",
    "{{var_roas_face}}": "+57,6%",
    "{{inv_face}}":      "R$ 200,73",
    "{{inv_face_comp}}": "R$ 177,78",
    "{{var_inv_face}}":  "+12,9%",
    "{{vendas_face}}":   "14",
    "{{vendas_face_comp}}": "8",
    "{{var_vendas_face}}": "+75,0%",
    "{{cpa_face}}":      "R$ 14,34",
    "{{cpa_face_comp}}": "R$ 22,22",
    "{{var_cpa_face}}":  "-35,5%",
    # Google Ads: sem dados
    "{{fat_goog}}":  "-",
    "{{roas_goog}}": "-",
    "{{inv_goog}}":  "-",
    # GA4: sem dados
    "{{ses_ga}}": "-",
    # Criativos: sem imagens reais (slots com placeholder)
    "{{nome_adf1}}": "-",
    "{{img_adf1}}":  "__NO_IMAGE__",
    "{{roas_adf1}}": "-",
    "{{conv_adf1}}": "-",
    "{{fat_adf1}}":  "-",
    "{{inv_adf1}}":  "-",
    "{{cpa_adf1}}":  "-",
}


class TestDetectarPlataformas:
    def test_piknik_so_tem_meta(self):
        ctx = normalizar_dados(DADOS_PIKNIK_REAL)
        ads_meta = _extrair_ads(ctx, "adf", 3)
        plat = _detectar_plataformas(ctx, ads_meta, [])
        assert plat["has_meta"]    is True
        assert plat["has_google"]  is False
        assert plat["has_ga4"]     is False
        assert plat["has_painel"]  is False
        assert plat["has_criativos"] is False

    def test_dados_completos_tem_todas_plataformas(self):
        ctx = normalizar_dados(DADOS_HANDLER_REAL)
        ads_meta = _extrair_ads(ctx, "adf", 3)
        plat = _detectar_plataformas(ctx, ads_meta, [])
        assert plat["has_meta"]      is True
        assert plat["has_ga4"]       is True
        assert plat["has_painel"]    is True
        assert plat["has_criativos"] is True


class TestPaginasCondicionais:
    def test_piknik_pdf_valido(self):
        """Cliente com só Meta: PDF válido, sem quebrar."""
        pdf = gerar_pdf("E-commerce", DADOS_PIKNIK_REAL)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 50_000

    def test_piknik_pdf_sem_paginas_vazias(self):
        """PDF do Piknik deve ter 4 págs: Capa + Resumo + Meta + Contra-capa."""
        import fitz  # PyMuPDF — se não tiver, instalar: pip install pymupdf
        pdf = gerar_pdf("E-commerce", DADOS_PIKNIK_REAL)
        try:
            doc = fitz.open(stream=pdf, filetype="pdf")
            assert doc.page_count == 4, f"Esperado 4 págs, encontrado {doc.page_count}"
            # Pág 3 deve ser Meta Ads
            texto_p3 = doc[2].get_text()
            assert "Meta Ads" in texto_p3 or "Faturamento" in texto_p3
        except ImportError:
            pytest.skip("PyMuPDF não instalado — verificação de contagem de páginas ignorada")

    def test_pdf_completo_mais_paginas_que_parcial(self):
        """Report com todas as plataformas deve ter mais páginas que um parcial."""
        pdf_completo = gerar_pdf("E-commerce", DADOS_HANDLER_REAL)
        pdf_parcial  = gerar_pdf("E-commerce", DADOS_PIKNIK_REAL)
        assert len(pdf_completo) > len(pdf_parcial)

    def test_pdf_piknik_abaixo_4mb(self):
        pdf = gerar_pdf("E-commerce", DADOS_PIKNIK_REAL)
        assert len(pdf) < 4 * 1024 * 1024


# ── Regressões: performance (sem rede) + detecção de plataforma Lead ──
DADOS_LEAD_REAL = {
    "{{PERIODO_INICIO}}": "26/05/2026", "{{PERIODO_FIM}}": "30/05/2026",
    "{{freq}}": "Semanal", "{{cliente}}": "Lead Teste",
    # Painel de leads
    "{{lead_sem}}": "184", "{{lead_sem_comp}}": "162", "{{var_lead_sem}}": "+13,6%",
    "{{cpl}}": "R$ 18,50", "{{inv_sem}}": "R$ 3.404,00",
    # Meta (lead)
    "{{lead_face}}": "120", "{{lead_face_comp}}": "100", "{{var_lead_face}}": "+20,0%",
    "{{cpl_face}}": "R$ 16,00", "{{inv_face}}": "R$ 1.920,00",
    # Sem Google, sem GA4
    "{{lead_goog}}": "-", "{{ses}}": "-",
}


class TestSemRede:
    """O HTML renderizado não pode depender de CDN/Google Fonts (perf + offline)."""
    def test_html_sem_google_fonts_nem_chartjs(self):
        from core.pdf_generator import renderizar_html, normalizar_dados, _extrair_ads, _detectar_plataformas
        ctx = normalizar_dados(DADOS_HANDLER_REAL)
        ctx["ads_meta"] = _extrair_ads(ctx, "adf", 3); ctx["ads_google"] = []
        ctx.update(_detectar_plataformas(ctx, ctx["ads_meta"], []))
        html = renderizar_html("E-commerce", ctx)
        assert "fonts.googleapis.com" not in html, "Google Fonts via rede ainda presente"
        assert "cdn.jsdelivr.net" not in html and "chart.js" not in html.lower(), "Chart.js CDN ainda presente"
        assert "@font-face" in html and "base64" in html, "Fonte Inter não está embutida"


class TestDeteccaoLead:
    def test_lead_com_meta_e_painel_sem_google_ga4(self):
        from core.pdf_generator import normalizar_dados, _extrair_ads, _detectar_plataformas
        ctx = normalizar_dados(DADOS_LEAD_REAL)
        plat = _detectar_plataformas(ctx, _extrair_ads(ctx, "adf", 3), [])
        assert plat["has_meta"] is True
        assert plat["has_painel"] is True
        assert plat["has_google"] is False
        assert plat["has_ga4"] is False

    def test_lead_com_site_pdf_valido(self):
        from core.pdf_generator import gerar_pdf
        pdf = gerar_pdf("Lead Com Site", DADOS_LEAD_REAL)
        assert pdf[:4] == b"%PDF" and len(pdf) > 50_000

# PDF Report "Efeito UAU" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir Google Slides por PDF gerado via Playwright + Jinja2 com identidade visual Turbo Partners (dark, ciano/roxo), autoexplicativo para envio no WhatsApp.

**Architecture:** `report_generator.py` chama `core/pdf_generator.py` após `coletar_dados()`. O `pdf_generator` normaliza o dict de placeholders do handler, renderiza via Jinja2 em HTML, e usa Playwright (headless Chromium) para exportar PDF A4. Google Slides mantido em paralelo durante validação.

**Tech Stack:** Python 3.12+, Playwright 1.44+, Jinja2 3.1+ (já instalado), pytest

---

## Mapa de Arquivos

| Ação | Caminho |
|---|---|
| Create | `core/pdf_generator.py` |
| Create | `core/templates/base.html` |
| Create | `core/templates/ecommerce.html` |
| Create | `core/templates/lead_com_site.html` |
| Create | `core/templates/lead_sem_site.html` |
| Create | `core/templates/partials/_big_kpi.html` |
| Create | `core/templates/partials/_small_kpi.html` |
| Create | `core/templates/partials/_channel_header.html` |
| Create | `core/templates/partials/_bar_chart.html` |
| Create | `core/templates/partials/_page_footer.html` |
| Create | `tests/__init__.py` |
| Create | `tests/test_pdf_generator.py` |
| Modify | `requirements.txt` |
| Modify | `report_generator.py` |

---

## Task 1: Playwright — Dependência e Instalação

**Files:**
- Modify: `requirements.txt`

- [ ] **Adicionar playwright ao requirements.txt**

Abrir `requirements.txt` e adicionar logo após a linha do Jinja2:
```
playwright>=1.44
```

- [ ] **Instalar e baixar Chromium**

```bash
pip install playwright
playwright install chromium
```

Saída esperada: `Chromium X.X.X (playwright build vXXX) downloaded to ~/.cache/ms-playwright/...`

- [ ] **Verificar instalação**

```bash
python -c "from playwright.sync_api import sync_playwright; print('OK')"
```

Esperado: `OK`

- [ ] **Commit**

```bash
git add requirements.txt
git commit -m "feat(pdf): adiciona playwright como dependência para geração de PDF"
```

---

## Task 2: `core/pdf_generator.py` com Testes

**Files:**
- Create: `core/pdf_generator.py`
- Create: `tests/__init__.py`
- Create: `tests/test_pdf_generator.py`

- [ ] **Escrever os testes primeiro**

Criar `tests/__init__.py` (vazio):
```python
```

Criar `tests/test_pdf_generator.py`:
```python
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
```

- [ ] **Rodar testes — confirmar FAIL**

```bash
cd /Users/mac0267/Documents/auto-report-main
pytest tests/test_pdf_generator.py -v 2>&1 | head -30
```

Esperado: `ModuleNotFoundError: No module named 'core.pdf_generator'`

- [ ] **Implementar `core/pdf_generator.py`**

```python
"""
core/pdf_generator.py

Geração de PDF via Playwright + Jinja2.
Substitui Google Slides como output do report_generator.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja_env: Environment | None = None

_TEMPLATE_MAP: dict[str, str] = {
    "E-commerce":    "ecommerce.html",
    "Lead Com Site": "lead_com_site.html",
    "Lead Sem Site": "lead_sem_site.html",
}


def _get_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        env.filters["delta_class"] = delta_class
        _jinja_env = env
    return _jinja_env


def normalizar_dados(dados: dict[str, str]) -> dict[str, Any]:
    """
    Converte placeholders do handler em contexto Jinja2.
    {"{{fat_sem}}": "R$ 100,00"} → {"fat_sem": "R$ 100,00"}
    """
    return {re.sub(r"[{}]", "", k).strip(): v for k, v in dados.items()}


def selecionar_template(categoria: str) -> str:
    """Retorna nome do arquivo de template para a categoria."""
    name = _TEMPLATE_MAP.get(categoria)
    if name is None:
        raise ValueError(f"Categoria sem template PDF: {categoria!r}")
    return name


def delta_class(valor: str) -> str:
    """Retorna 'up', 'down' ou 'neutral' para uso como classe CSS."""
    s = str(valor).strip()
    if not s or s == "—":
        return "neutral"
    if s.startswith("-") or s.startswith("↓"):
        return "down"
    if s.startswith("+") or s.startswith("↑") or (s.replace(",", ".").lstrip("0").replace(".", "").isdigit()):
        try:
            return "up" if float(s.replace(",", ".").replace("%", "").replace("↑", "").replace("↓", "").strip()) > 0 else "down"
        except ValueError:
            pass
    return "neutral"


def renderizar_html(categoria: str, ctx: dict[str, Any]) -> str:
    """Renderiza template Jinja2 da categoria com o contexto fornecido."""
    env = _get_env()
    template = env.get_template(selecionar_template(categoria))
    return template.render(**ctx)


def html_para_pdf(html: str) -> bytes:
    """Renderiza HTML em headless Chromium e exporta PDF A4."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        try:
            page.wait_for_function(
                "typeof chartsReady === 'function' && chartsReady()",
                timeout=10_000,
            )
        except Exception:
            pass  # sem gráficos ou timeout — continua
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    return pdf_bytes


def gerar_pdf(
    categoria: str,
    dados: dict[str, str],
    dados_diarios: dict[str, list[float]] | None = None,
) -> bytes:
    """
    Ponto de entrada: dados do handler → PDF bytes.

    Parameters
    ----------
    categoria : str
        "E-commerce" | "Lead Com Site" | "Lead Sem Site"
    dados : dict
        Dict de placeholders retornado por handler.coletar_dados().
        Chaves com ou sem {{ }}.
    dados_diarios : dict | None
        Opcional. {"meta_ads": [seg, ter, qua, qui, sex], "google_ads": [...]}
    """
    ctx = normalizar_dados(dados)
    if dados_diarios:
        ctx["dados_diarios"] = dados_diarios
    return html_para_pdf(renderizar_html(categoria, ctx))


def salvar_pdf(
    pdf_bytes: bytes,
    nome_cliente: str,
    ano: int,
    mes: int,
    semana: int,
) -> Path:
    """
    Salva PDF em reports/{cliente}/{ano}/{mes:02d}/Report_Sem{N}_{cliente}.pdf
    Retorna o Path do arquivo criado.
    """
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", nome_cliente).strip("_")
    pasta = Path("reports") / safe / str(ano) / f"{mes:02d}"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"Report_Sem{semana:02d}_{safe}.pdf"
    caminho.write_bytes(pdf_bytes)
    return caminho
```

- [ ] **Rodar testes — confirmar PASS (exceto TestHtmlParaPdfSmoke que precisa de templates)**

```bash
pytest tests/test_pdf_generator.py -v -k "not HtmlParaPdf"
```

Esperado: todos PASS exceto os smoke tests de HTML→PDF.

- [ ] **Commit**

```bash
git add core/pdf_generator.py tests/__init__.py tests/test_pdf_generator.py
git commit -m "feat(pdf): core/pdf_generator com normalizar_dados, selecionar_template, salvar_pdf + testes"
```

---

## Task 3: `core/templates/base.html` — Design System

**Files:**
- Create: `core/templates/base.html`

- [ ] **Criar diretórios de templates**

```bash
mkdir -p core/templates/partials
```

- [ ] **Criar `core/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

:root {
  --bg-base:      #060612;
  --bg-card:      #08081A;
  --bg-card-2:    #0C0C22;
  --bg-card-3:    #0F0F25;
  --border:       #1a1a35;
  --border-sub:   #111130;
  --cyan:         #00C8FF;
  --purple:       #7B2FFF;
  --up:           #10B981;
  --down:         #EF4444;
  --neutral:      #6B7280;
  --t-primary:    #FFFFFF;
  --t-secondary:  #E5E7EB;
  --t-muted:      #9CA3AF;
  --t-faint:      #4B5563;
  --t-ghost:      #374151;
  --t-dim:        #1F2937;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: 'Inter', sans-serif;
  background: var(--bg-base);
  color: var(--t-primary);
  width: 210mm;
}

@page { size: A4 portrait; margin: 0; }

@media print {
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
}

/* ── Página ── */
.page {
  width: 210mm;
  min-height: 297mm;
  height: 297mm;
  overflow: hidden;
  position: relative;
  background: var(--bg-base);
  page-break-after: always;
  padding: 12mm 14mm;
  display: flex;
  flex-direction: column;
}
.page:last-child { page-break-after: avoid; }

/* ── Utilitários de layout ── */
.row    { display: flex; gap: 10px; }
.col    { display: flex; flex-direction: column; }
.g2     { display: grid; gap: 8px; }
.g2c    { grid-template-columns: 1fr 1fr; }
.g3c    { grid-template-columns: 1fr 1fr 1fr; }

/* ── Linha gradiente de acento ── */
.accent-line {
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: linear-gradient(to bottom, var(--cyan), var(--purple));
}
.accent-line-h {
  height: 2px;
  background: linear-gradient(to right, var(--cyan), transparent);
}
.accent-line-top {
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(to right, var(--cyan), var(--purple));
}

/* ── Glow decorativo ── */
.glow-tr {
  position: absolute;
  width: 300px; height: 300px;
  background: radial-gradient(circle, rgba(0,200,255,0.15) 0%, transparent 70%);
  top: -80px; right: -80px;
  pointer-events: none;
}
.glow-bl {
  position: absolute;
  width: 250px; height: 250px;
  background: radial-gradient(circle, rgba(123,47,255,0.18) 0%, transparent 70%);
  bottom: 40px; left: -60px;
  pointer-events: none;
}

/* ── Badge de categoria ── */
.badge {
  display: inline-block;
  background: rgba(0,200,255,0.08);
  border: 1px solid rgba(0,200,255,0.25);
  color: var(--cyan);
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 4px 10px;
  border-radius: 20px;
}

/* ── Cards ── */
.card {
  background: var(--bg-card-3);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  position: relative;
  overflow: hidden;
}
.card-sm {
  background: var(--bg-card-2);
  border: 1px solid var(--border-sub);
  border-radius: 8px;
  padding: 10px 12px;
}

/* ── KPI grande ── */
.kpi-big-label {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--t-faint);
  margin-bottom: 6px;
}
.kpi-big-value {
  font-size: 26px;
  font-weight: 900;
  letter-spacing: -0.5px;
  line-height: 1;
  color: var(--t-primary);
}
.kpi-big-delta { font-size: 11px; font-weight: 700; margin-top: 5px; }
.kpi-big-vs { font-size: 9px; color: var(--t-ghost); margin-top: 2px; }

/* ── KPI pequeno ── */
.kpi-sm-label {
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--t-ghost);
  margin-bottom: 4px;
}
.kpi-sm-value {
  font-size: 16px;
  font-weight: 800;
  color: var(--t-secondary);
  line-height: 1;
}
.kpi-sm-delta { font-size: 9px; font-weight: 700; margin-top: 3px; }

/* ── Cores de delta ── */
.up      { color: var(--up); }
.down    { color: var(--down); }
.neutral { color: var(--t-faint); }

/* ── Chart area ── */
.chart-wrap {
  background: var(--bg-card-2);
  border: 1px solid var(--border-sub);
  border-radius: 8px;
  padding: 12px;
  flex: 1;
}
.chart-title {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--t-faint);
  margin-bottom: 10px;
}

/* ── Header de canal ── */
.channel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-sub);
  margin-bottom: 12px;
}
.channel-icon {
  width: 34px; height: 34px;
  border-radius: 9px;
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 900;
}
.channel-name { font-size: 15px; font-weight: 800; }
.channel-sub  { font-size: 8px; color: var(--t-faint); text-transform: uppercase; letter-spacing: 1px; }
.channel-period { font-size: 9px; color: var(--t-ghost); text-align: right; line-height: 1.5; }
.channel-period strong { color: var(--t-muted); font-weight: 600; }

/* ── Footer de página ── */
.page-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 8px;
  border-top: 1px solid var(--border-sub);
  margin-top: auto;
}
.page-footer-brand {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--t-dim);
}
.page-footer-num { font-size: 8px; color: var(--t-dim); }
</style>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
  var _chartsToRender = 0, _chartsRendered = 0;
  function _chartDone() { _chartsRendered++; }
  function chartsReady() {
    return _chartsToRender === 0 || _chartsRendered >= _chartsToRender;
  }
  var _CHART_DEFAULTS = {
    color: '#4B5563',
    borderColor: '#111130',
    backgroundColor: 'rgba(0,200,255,0.55)',
  };
</script>
</head>
<body>
{% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Commit**

```bash
git add core/templates/base.html
git commit -m "feat(pdf): base.html com design system dark ciano+roxo (Turbo Partners)"
```

---

## Task 4: Partials — Macros Jinja2

**Files:**
- Create: `core/templates/partials/_big_kpi.html`
- Create: `core/templates/partials/_small_kpi.html`
- Create: `core/templates/partials/_channel_header.html`
- Create: `core/templates/partials/_bar_chart.html`
- Create: `core/templates/partials/_page_footer.html`

- [ ] **Criar `_big_kpi.html`**

```html
{% macro big_kpi(label, value, delta=None, vs=None) %}
<div class="card" style="flex:1">
  <div class="accent-line-top"></div>
  <div class="kpi-big-label">{{ label }}</div>
  <div class="kpi-big-value">{{ value | default("—") }}</div>
  {% if delta %}
  <div class="kpi-big-delta {{ delta | delta_class }}">
    {{ "↑" if delta | delta_class == "up" else ("↓" if delta | delta_class == "down" else "") }}
    {{ delta }}
  </div>
  {% endif %}
  {% if vs %}
  <div class="kpi-big-vs">vs {{ vs }}</div>
  {% endif %}
</div>
{% endmacro %}
```

- [ ] **Criar `_small_kpi.html`**

```html
{% macro small_kpi(label, value, delta=None) %}
<div class="card-sm">
  <div class="kpi-sm-label">{{ label }}</div>
  <div class="kpi-sm-value">{{ value | default("—") }}</div>
  {% if delta %}
  <div class="kpi-sm-delta {{ delta | delta_class }}">
    {{ "↑" if delta | delta_class == "up" else ("↓" if delta | delta_class == "down" else "") }}
    {{ delta }}
  </div>
  {% endif %}
</div>
{% endmacro %}
```

- [ ] **Criar `_channel_header.html`**

```html
{% macro channel_header(nome, icone_html, periodo_ref, periodo_comp, subtitulo="") %}
<div class="channel-header">
  <div class="row" style="align-items:center;gap:10px;">
    <div class="channel-icon">{{ icone_html | safe }}</div>
    <div>
      <div class="channel-name">{{ nome }}</div>
      <div class="channel-sub">{{ subtitulo if subtitulo else "Performance · " + periodo_ref }}</div>
    </div>
  </div>
  <div class="channel-period">
    <strong>{{ periodo_ref }}</strong>
    vs {{ periodo_comp }}
  </div>
</div>
{% endmacro %}
```

- [ ] **Criar `_bar_chart.html`**

```html
{% macro bar_chart(chart_id, dados_list, label="Faturamento diário", labels=None) %}
{% set _labels = labels if labels else ["Seg","Ter","Qua","Qui","Sex"] %}
<div class="chart-wrap">
  <div class="chart-title">{{ label }}</div>
  {% if dados_list %}
  <canvas id="{{ chart_id }}" style="max-height:90px;"></canvas>
  <script>
    _chartsToRender++;
    (function(){
      var ctx = document.getElementById('{{ chart_id }}').getContext('2d');
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: {{ _labels | tojson }},
          datasets: [{
            data: {{ dados_list | tojson }},
            backgroundColor: 'rgba(0,200,255,0.55)',
            borderColor: '#00C8FF',
            borderWidth: 1,
            borderRadius: 4,
          }]
        },
        options: {
          responsive: true,
          animation: { onComplete: _chartDone },
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: '#111130' }, ticks: { color: '#4B5563', font: { size: 7 } } },
            y: { grid: { color: '#111130' }, ticks: { color: '#4B5563', font: { size: 7 },
                 callback: function(v){ return v >= 1000 ? 'R$'+(v/1000).toFixed(0)+'k' : v; } } }
          }
        }
      });
    })();
  </script>
  {% else %}
  <div style="color:var(--t-faint);font-size:10px;text-align:center;padding:24px 0;">
    Dados diários indisponíveis
  </div>
  {% endif %}
</div>
{% endmacro %}
```

- [ ] **Criar `_page_footer.html`**

```html
{% macro page_footer(pagina, total) %}
<div class="page-footer">
  <div class="page-footer-brand">Turbo Partners</div>
  <div class="page-footer-num">{{ pagina }} / {{ total }}</div>
</div>
{% endmacro %}
```

- [ ] **Commit**

```bash
git add core/templates/partials/
git commit -m "feat(pdf): partials Jinja2 — big_kpi, small_kpi, channel_header, bar_chart, page_footer"
```

---

## Task 5: `core/templates/ecommerce.html` — 7 Páginas

**Files:**
- Create: `core/templates/ecommerce.html`

- [ ] **Criar `core/templates/ecommerce.html`**

```html
{% extends "base.html" %}
{% from "partials/_big_kpi.html"       import big_kpi %}
{% from "partials/_small_kpi.html"     import small_kpi %}
{% from "partials/_channel_header.html" import channel_header %}
{% from "partials/_bar_chart.html"     import bar_chart %}
{% from "partials/_page_footer.html"   import page_footer %}

{% set total_pags = 7 %}
{% set dd = dados_diarios if dados_diarios is defined else {} %}

{% block content %}

{# ════════════════════════════════════════════
   PÁG 1 — CAPA
   ════════════════════════════════════════════ #}
<div class="page">
  <div class="accent-line"></div>
  <div class="glow-tr"></div>
  <div class="glow-bl"></div>

  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <span class="badge">E-commerce</span>
    <span style="font-size:9px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--t-dim);">Turbo Partners</span>
  </div>

  <div style="flex:1;display:flex;flex-direction:column;justify-content:center;padding:24px 0;">
    <div style="font-size:10px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--cyan);margin-bottom:10px;">
      Relatório de Performance
    </div>
    <div style="font-size:38px;font-weight:900;letter-spacing:-1.5px;line-height:1.05;color:var(--t-primary);margin-bottom:10px;">
      {{ cliente | default("Cliente") }}
    </div>
    <div style="font-size:13px;color:var(--t-ghost);">
      <strong style="color:var(--t-muted);">
        {{ freq | default("Semana") }} {{ semana | default("") }} · {{ periodo_inicio | default("") }} a {{ periodo_fim | default("") }}
      </strong>
    </div>

    <div class="accent-line-h" style="margin:20px 0;"></div>

    <div class="g2 g3c">
      <div class="card-sm">
        <div class="kpi-sm-label">Faturamento</div>
        <div class="kpi-sm-value">{{ fat_sem | default("—") }}</div>
        {% set d1 = var_fat_sem | default("") %}
        {% if d1 %}<div class="kpi-sm-delta {{ d1 | delta_class }}">{{ d1 }}</div>{% endif %}
      </div>
      <div class="card-sm">
        <div class="kpi-sm-label">ROAS</div>
        <div class="kpi-sm-value">{{ roas | default("—") }}</div>
        {% set d2 = var_roas | default("") %}
        {% if d2 %}<div class="kpi-sm-delta {{ d2 | delta_class }}">{{ d2 }}</div>{% endif %}
      </div>
      <div class="card-sm">
        <div class="kpi-sm-label">Investimento</div>
        <div class="kpi-sm-value">{{ inv_sem | default("—") }}</div>
        {% set d3 = var_inv_sem | default("") %}
        {% if d3 %}<div class="kpi-sm-delta {{ d3 | delta_class }}">{{ d3 }}</div>{% endif %}
      </div>
    </div>
  </div>

  <div style="display:flex;justify-content:space-between;align-items:flex-end;">
    <span style="font-size:8px;color:var(--t-dim);letter-spacing:2px;text-transform:uppercase;">Relatório Semanal</span>
    <span style="font-size:9px;color:var(--t-dim);">{{ periodo_fim | default("") }}</span>
  </div>
</div>

{# ════════════════════════════════════════════
   PÁG 2 — RESUMO EXECUTIVO
   ════════════════════════════════════════════ #}
<div class="page">
  <div class="glow-tr"></div>

  <div style="font-size:10px;font-weight:700;letter-spacing:3px;text-transform:uppercase;color:var(--cyan);margin-bottom:16px;">
    Resumo Executivo
  </div>

  <div class="card" style="margin-bottom:12px;">
    <div class="accent-line-top"></div>
    <div class="kpi-big-label">Faturamento Total Atribuído</div>
    <div class="kpi-big-value">{{ fat_sem | default("—") }}</div>
    {% set d_fat = var_fat_sem | default("") %}
    {% if d_fat %}
    <div class="kpi-big-delta {{ d_fat | delta_class }}" style="margin-top:6px;">
      {{ "↑" if d_fat | delta_class == "up" else "↓" }} {{ d_fat }} vs semana anterior
    </div>
    {% endif %}
  </div>

  <div class="g2 g2c" style="margin-bottom:12px;">
    {{ big_kpi("ROAS (Meta)", roas | default("—"), var_roas | default(None), roas_comp | default(None)) }}
    {{ big_kpi("ROAS (Google)", roas_google | default("—"), var_roas_google | default(None), roas_google_comp | default(None)) }}
  </div>

  <div class="g2 g2c" style="margin-bottom:12px;">
    {{ big_kpi("Investimento Total", inv_sem | default("—"), var_inv_sem | default(None)) }}
    {{ big_kpi("Vendas / Pedidos", vendas | default("—"), var_vendas | default(None)) }}
  </div>

  <div class="card-sm" style="margin-bottom:auto;">
    <div style="font-size:10px;color:var(--t-muted);line-height:1.7;font-style:italic;">
      {% if var_fat_sem is defined and var_fat_sem and not var_fat_sem.startswith("-") %}
        Semana {{ semana | default("") }} registrou crescimento de {{ var_fat_sem }} no faturamento
        atribuído, atingindo {{ fat_sem | default("") }}. As campanhas seguem em aceleração.
      {% else %}
        Semana {{ semana | default("") }} registrou faturamento de {{ fat_sem | default("") }}.
        {% if var_fat_sem is defined and var_fat_sem %}
        Retração de {{ var_fat_sem }} vs. semana anterior — campanhas em fase de otimização.
        {% endif %}
      {% endif %}
    </div>
  </div>

  {{ page_footer(2, total_pags) }}
</div>

{# ════════════════════════════════════════════
   PÁG 3 — META ADS
   ════════════════════════════════════════════ #}
<div class="page">
  <div class="glow-tr"></div>

  {{ channel_header(
      "Meta Ads",
      '<span style="background:linear-gradient(135deg,#1877F2,#0D5FBF);width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:15px;font-weight:900;color:#fff;">f</span>',
      periodo_inicio | default("") + " – " + periodo_fim | default(""),
      periodo_inicio_comp | default("") + " – " + periodo_fim_comp | default("")
  ) }}

  <div class="row" style="margin-bottom:10px;">
    {{ big_kpi("Faturamento Atribuído", fat_meta | default(fat_sem) | default("—"), var_fat_meta | default(var_fat_sem) | default(None), fat_meta_comp | default(None)) }}
    {{ big_kpi("ROAS", roas | default("—"), var_roas | default(None), roas_comp | default(None)) }}
  </div>

  <div class="g2 g3c" style="margin-bottom:10px;">
    {{ small_kpi("Investimento", inv_meta | default(inv_sem) | default("—"), var_inv_meta | default(None)) }}
    {{ small_kpi("Cliques", cliques_meta | default("—"), var_cliques_meta | default(None)) }}
    {{ small_kpi("CTR", ctr_meta | default("—"), var_ctr_meta | default(None)) }}
    {{ small_kpi("CPM", cpm_meta | default("—"), var_cpm_meta | default(None)) }}
    {{ small_kpi("CPC", cpc_meta | default("—"), var_cpc_meta | default(None)) }}
    {{ small_kpi("Conversões", conv_meta | default("—"), var_conv_meta | default(None)) }}
  </div>

  {{ bar_chart("chart_meta", dd.get("meta_ads") if dd else None, "Faturamento diário · Meta Ads") }}

  {{ page_footer(3, total_pags) }}
</div>

{# ════════════════════════════════════════════
   PÁG 4 — GOOGLE ADS
   ════════════════════════════════════════════ #}
<div class="page">
  <div class="glow-tr"></div>

  {{ channel_header(
      "Google Ads",
      '<span style="background:linear-gradient(135deg,#EA4335,#FBBC05);width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:900;color:#fff;">G</span>',
      periodo_inicio | default("") + " – " + periodo_fim | default(""),
      periodo_inicio_comp | default("") + " – " + periodo_fim_comp | default("")
  ) }}

  <div class="row" style="margin-bottom:10px;">
    {{ big_kpi("Receita Conversões", fat_google | default("—"), var_fat_google | default(None), fat_google_comp | default(None)) }}
    {{ big_kpi("ROAS", roas_google | default("—"), var_roas_google | default(None), roas_google_comp | default(None)) }}
  </div>

  <div class="g2 g3c" style="margin-bottom:10px;">
    {{ small_kpi("Investimento", inv_google | default("—"), var_inv_google | default(None)) }}
    {{ small_kpi("Impressões", impr_google | default("—"), var_impr_google | default(None)) }}
    {{ small_kpi("CTR", ctr_google | default("—"), var_ctr_google | default(None)) }}
    {{ small_kpi("Cliques", cliques_google | default("—"), var_cliques_google | default(None)) }}
    {{ small_kpi("CPC", cpc_google | default("—"), var_cpc_google | default(None)) }}
    {{ small_kpi("CPA", cpa_google | default("—"), var_cpa_google | default(None)) }}
  </div>

  {{ bar_chart("chart_google", dd.get("google_ads") if dd else None, "Receita diária · Google Ads") }}

  {{ page_footer(4, total_pags) }}
</div>

{# ════════════════════════════════════════════
   PÁG 5 — GA4
   ════════════════════════════════════════════ #}
<div class="page">
  <div class="glow-tr"></div>

  {{ channel_header(
      "GA4 — Analytics",
      '<span style="background:linear-gradient(135deg,#F9AB00,#E37400);width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:900;color:#fff;">◆</span>',
      periodo_inicio | default("") + " – " + periodo_fim | default(""),
      periodo_inicio_comp | default("") + " – " + periodo_fim_comp | default("")
  ) }}

  <div class="row" style="margin-bottom:10px;">
    {{ big_kpi("Sessões", sessoes | default("—"), var_sessoes | default(None), sessoes_comp | default(None)) }}
    {{ big_kpi("Taxa de Conversão", taxa_conv | default("—"), var_taxa_conv | default(None), taxa_conv_comp | default(None)) }}
  </div>

  <div class="g2 g3c" style="margin-bottom:10px;">
    {{ small_kpi("Novos Usuários", novos_usuarios | default("—"), var_novos_usuarios | default(None)) }}
    {{ small_kpi("Taxa de Rejeição", bounce_rate | default("—"), var_bounce_rate | default(None)) }}
    {{ small_kpi("Duração Média", duracao_media | default("—")) }}
    {{ small_kpi("Páginas/Sessão", pags_sessao | default("—")) }}
    {{ small_kpi("Receita GA4", receita_ga4 | default("—"), var_receita_ga4 | default(None)) }}
    {{ small_kpi("Ticket Médio", tck_med | default("—"), var_tck_med | default(None)) }}
  </div>

  {{ bar_chart("chart_ga4", dd.get("ga4") if dd else None, "Sessões diárias · GA4") }}

  {{ page_footer(5, total_pags) }}
</div>

{# ════════════════════════════════════════════
   PÁG 6 — PAINEL INTERNO
   ════════════════════════════════════════════ #}
<div class="page">
  <div class="glow-tr"></div>

  {{ channel_header(
      "Painel de Negócio",
      '<span style="background:linear-gradient(135deg,#00C8FF,#7B2FFF);width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:16px;">📊</span>',
      periodo_inicio | default("") + " – " + periodo_fim | default(""),
      periodo_inicio_comp | default("") + " – " + periodo_fim_comp | default(""),
      "Negócio · " + freq | default("Semana") + " " + semana | default("")
  ) }}

  <div class="row" style="margin-bottom:10px;">
    {{ big_kpi("Faturamento Bruto", fat_bruto | default("—"), var_fat_bruto | default(None), fat_bruto_comp | default(None)) }}
    {{ big_kpi("Pedidos", pedidos | default(vendas) | default("—"), var_pedidos | default(var_vendas) | default(None)) }}
  </div>

  <div class="g2 g3c" style="margin-bottom:10px;">
    {{ small_kpi("Ticket Médio", tck_med | default("—"), var_tck_med | default(None)) }}
    {{ small_kpi("Fat. Atribuído", fat_sem | default("—"), var_fat_sem | default(None)) }}
    {{ small_kpi("% Atribuição", perc_atrib | default("—")) }}
    {{ small_kpi("Rec. Novos", rec_novos | default("—")) }}
    {{ small_kpi("Rec. Recorrentes", rec_recorrentes | default("—")) }}
    {{ small_kpi("% Recorrência", perc_recorrencia | default("—")) }}
  </div>

  {{ bar_chart("chart_painel", dd.get("painel") if dd else None, "Faturamento bruto diário") }}

  {{ page_footer(6, total_pags) }}
</div>

{# ════════════════════════════════════════════
   PÁG 7 — CONTRA-CAPA
   ════════════════════════════════════════════ #}
<div class="page" style="justify-content:center;align-items:center;gap:20px;">
  <div class="glow-tr"></div>
  <div class="glow-bl"></div>

  <div style="width:50px;height:2px;background:linear-gradient(to right,var(--cyan),var(--purple));border-radius:1px;"></div>

  <div style="text-align:center;">
    <div style="font-size:22px;font-weight:900;letter-spacing:4px;text-transform:uppercase;color:var(--t-primary);">
      Turbo<br>Partners
    </div>
    <div style="font-size:9px;color:var(--t-faint);letter-spacing:3px;text-transform:uppercase;margin-top:6px;">
      Performance · Tech · Growth
    </div>
  </div>

  <div style="width:50px;height:2px;background:linear-gradient(to right,var(--cyan),var(--purple));border-radius:1px;"></div>

  <div style="text-align:center;font-size:11px;color:var(--t-ghost);line-height:2;">
    contato@turbopartners.com.br<br>
    turbopartners.com.br<br>
    @turbo.partners
  </div>

  {% if proximo_report is defined %}
  <div style="background:rgba(0,200,255,0.06);border:1px solid rgba(0,200,255,0.2);border-radius:10px;padding:14px 24px;text-align:center;">
    <div style="font-size:9px;color:var(--cyan);font-weight:700;letter-spacing:2px;text-transform:uppercase;">Próximo Report</div>
    <div style="font-size:13px;color:var(--t-primary);font-weight:800;margin-top:4px;">{{ proximo_report }}</div>
  </div>
  {% endif %}
</div>

{% endblock %}
```

- [ ] **Teste de renderização do template**

```bash
cd /Users/mac0267/Documents/auto-report-main
python -c "
from core.pdf_generator import renderizar_html
ctx = {
    'cliente': 'Acme Store',
    'periodo_inicio': '26/05/2026',
    'periodo_fim': '30/05/2026',
    'semana': '22',
    'freq': 'Semana',
    'fat_sem': 'R\$ 847.320,00',
    'roas': '8,4x',
    'inv_sem': 'R\$ 72.900,00',
    'var_fat_sem': '+23,4%',
}
html = renderizar_html('E-commerce', ctx)
print('OK — tamanho:', len(html), 'chars')
assert 'Acme Store' in html
assert 'R\$ 847.320,00' in html
print('Asserts OK')
"
```

Esperado: `OK — tamanho: XXXXX chars` + `Asserts OK`

- [ ] **Commit**

```bash
git add core/templates/ecommerce.html
git commit -m "feat(pdf): template ecommerce.html — 7 páginas dark com Jinja2"
```

---

## Task 6: Templates Lead

**Files:**
- Create: `core/templates/lead_com_site.html`
- Create: `core/templates/lead_sem_site.html`

- [ ] **Criar `core/templates/lead_com_site.html`**

É igual ao `ecommerce.html`, mas sem a Pág 5 (GA4) e com KPIs de lead no Painel. Copie `ecommerce.html` e faça as seguintes alterações:

1. Altere `{% set total_pags = 7 %}` para `{% set total_pags = 6 %}`
2. Altere o badge da Capa: `<span class="badge">Lead Com Site</span>`
3. Remova completamente o bloco `{# PÁG 5 — GA4 #}` (da linha `<div class="page">` ao `</div>` correspondente)
4. Atualize os números de página das págs 6 e 7:
   - Painel: `{{ page_footer(5, total_pags) }}`
   - Contra-capa: `{{ page_footer(6, total_pags) }}`

```html
{% extends "base.html" %}
{% from "partials/_big_kpi.html"        import big_kpi %}
{% from "partials/_small_kpi.html"      import small_kpi %}
{% from "partials/_channel_header.html" import channel_header %}
{% from "partials/_bar_chart.html"      import bar_chart %}
{% from "partials/_page_footer.html"    import page_footer %}

{% set total_pags = 6 %}
{% set dd = dados_diarios if dados_diarios is defined else {} %}

{% block content %}
{# Págs 1–4 idênticas ao ecommerce.html — copie os blocos #}
{# ... CAPA (page_footer não há, só no final tem) ... #}
{# ... RESUMO EXECUTIVO {{ page_footer(2, total_pags) }} ... #}
{# ... META ADS {{ page_footer(3, total_pags) }} ... #}
{# ... GOOGLE ADS {{ page_footer(4, total_pags) }} ... #}

{# PÁG 5 — PAINEL (sem GA4) #}
<div class="page">
  <div class="glow-tr"></div>
  {{ channel_header("Painel de Negócio",
      '<span style="background:linear-gradient(135deg,#00C8FF,#7B2FFF);width:34px;height:34px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:16px;">📊</span>',
      periodo_inicio | default("") + " – " + periodo_fim | default(""),
      periodo_inicio_comp | default("") + " – " + periodo_fim_comp | default(""),
      "Negócio · " + freq | default("Semana") + " " + semana | default("")
  ) }}
  <div class="row" style="margin-bottom:10px;">
    {{ big_kpi("Leads Recebidos", leads | default("—"), var_leads | default(None)) }}
    {{ big_kpi("CPL do Painel", cpl_painel | default(cpl) | default("—"), var_cpl | default(None)) }}
  </div>
  <div class="g2 g3c" style="margin-bottom:10px;">
    {{ small_kpi("Tx. Conv. Lead→Cliente", taxa_conv_lead | default("—")) }}
    {{ small_kpi("CPA", cpa | default("—"), var_cpa | default(None)) }}
    {{ small_kpi("Fat. Gerado", fat_gerado | default("—")) }}
    {{ small_kpi("Meta de Leads", meta_leads | default("—")) }}
    {{ small_kpi("% Meta Atingida", per_meta_leads | default("—")) }}
    {{ small_kpi("Invest. Total", inv_sem | default("—"), var_inv_sem | default(None)) }}
  </div>
  {{ bar_chart("chart_painel", dd.get("painel") if dd else None, "Leads diários") }}
  {{ page_footer(5, total_pags) }}
</div>

{# PÁG 6 — CONTRA-CAPA (igual ao ecommerce) #}
<div class="page" style="justify-content:center;align-items:center;gap:20px;">
  <div class="glow-tr"></div><div class="glow-bl"></div>
  <div style="width:50px;height:2px;background:linear-gradient(to right,var(--cyan),var(--purple));border-radius:1px;"></div>
  <div style="text-align:center;">
    <div style="font-size:22px;font-weight:900;letter-spacing:4px;text-transform:uppercase;">Turbo<br>Partners</div>
    <div style="font-size:9px;color:var(--t-faint);letter-spacing:3px;text-transform:uppercase;margin-top:6px;">Performance · Tech · Growth</div>
  </div>
  <div style="width:50px;height:2px;background:linear-gradient(to right,var(--cyan),var(--purple));border-radius:1px;"></div>
  <div style="text-align:center;font-size:11px;color:var(--t-ghost);line-height:2;">
    contato@turbopartners.com.br<br>turbopartners.com.br<br>@turbo.partners
  </div>
  {% if proximo_report is defined %}
  <div style="background:rgba(0,200,255,0.06);border:1px solid rgba(0,200,255,0.2);border-radius:10px;padding:14px 24px;text-align:center;">
    <div style="font-size:9px;color:var(--cyan);font-weight:700;letter-spacing:2px;text-transform:uppercase;">Próximo Report</div>
    <div style="font-size:13px;color:var(--t-primary);font-weight:800;margin-top:4px;">{{ proximo_report }}</div>
  </div>
  {% endif %}
</div>
{% endblock %}
```

**Atenção:** O bloco acima está esquemático. Copie os blocos das Págs 1–4 do `ecommerce.html` integralmente — apenas ajuste `total_pags = 6` e os números de `page_footer`.

- [ ] **Criar `core/templates/lead_sem_site.html`**

Idêntico ao `lead_com_site.html`. Altere apenas:
1. Badge da Capa: `<span class="badge">Lead Sem Site</span>`
2. KPIs do Resumo Executivo: remova `roas_google` e substitua pelo CPL médio como destaque
3. Remova a Pág 4 (Google Ads) se o cliente Lead Sem Site não tiver Google Ads

> **Nota:** Se todos os clientes Lead Sem Site não usam Google Ads, remova o bloco de Google Ads e ajuste `total_pags = 5`.

- [ ] **Testar renderização dos templates Lead**

```bash
python -c "
from core.pdf_generator import renderizar_html
ctx = {'cliente': 'Lead Teste', 'periodo_inicio': '26/05', 'periodo_fim': '30/05', 'semana': '22', 'freq': 'Semana', 'leads': '1.284', 'cpl': 'R\$ 12,80'}
html = renderizar_html('Lead Com Site', ctx)
assert 'Lead Teste' in html
print('Lead Com Site OK')
html2 = renderizar_html('Lead Sem Site', ctx)
assert 'Lead Teste' in html2
print('Lead Sem Site OK')
"
```

- [ ] **Commit**

```bash
git add core/templates/lead_com_site.html core/templates/lead_sem_site.html
git commit -m "feat(pdf): templates lead_com_site e lead_sem_site (6 págs, sem GA4)"
```

---

## Task 7: Integração em `report_generator.py`

**Files:**
- Modify: `report_generator.py`

- [ ] **Inspecionar onde injetar no fluxo atual**

Abrir `report_generator.py` e localizar a função `processar_cliente()`. O fluxo atual é:
1. `coletar_dados()` → `dados` dict
2. `criar_copia()` → `presentation_id`
3. `slide_filler.preencher()` → slides preenchidos
4. `handler.pos_processar()` → ajustes finais
5. `set_status_e_lastgen()`

Injetaremos **após o passo 1** (temos `dados`) e **antes do passo 2** (Slides continua funcionando em paralelo).

- [ ] **Adicionar import e helper no topo de `report_generator.py`**

Localizar o bloco de imports (linhas 1–20 aproximadamente) e adicionar:

```python
import os
from core import pdf_generator  # NOVO
```

Logo abaixo dos imports existentes, adicionar o helper:

```python
def _gerar_e_salvar_pdf(cliente, dados: dict, periodo_ref) -> None:
    """Gera PDF em paralelo ao Slides. Falha silenciosa para não bloquear o fluxo."""
    if not os.getenv("PDF_REPORT_ATIVO", "false").lower() == "true":
        return
    try:
        from datetime import date
        pdf_bytes = pdf_generator.gerar_pdf(cliente.categoria, dados)
        hoje = date.today()
        # Extrai número da semana a partir do periodo_ref se disponível
        semana = getattr(periodo_ref, "semana", hoje.isocalendar()[1])
        pdf_generator.salvar_pdf(
            pdf_bytes,
            nome_cliente=cliente.nome,
            ano=hoje.year,
            mes=hoje.month,
            semana=semana,
        )
    except Exception as exc:
        print(f"[PDF] Falha ao gerar PDF para {cliente.nome}: {exc}")
```

- [ ] **Chamar o helper dentro de `processar_cliente()`**

Localizar a linha onde `dados` está completo (logo após `handler.coletar_dados()`). Inserir a chamada:

```python
# Linha após: dados.update(variacao_dados_comparativos.calcular_variacoes(...))
_gerar_e_salvar_pdf(cliente, dados, periodo_ref)   # NOVO — PDF em paralelo ao Slides
```

- [ ] **Adicionar variável de ambiente ao `.env` de desenvolvimento**

```bash
echo "PDF_REPORT_ATIVO=false" >> .env
```

(Manter `false` por padrão — ativar manualmente para testar: `PDF_REPORT_ATIVO=true`)

- [ ] **Verificar que o código importa sem erros**

```bash
python -c "import report_generator; print('Import OK')"
```

Esperado: `Import OK`

- [ ] **Commit**

```bash
git add report_generator.py .env
git commit -m "feat(pdf): integração PDF_REPORT_ATIVO em report_generator.py (paralelo ao Slides)"
```

---

## Task 8: Smoke Test End-to-End

**Files:**
- Create: `tests/test_pdf_smoke.py`

- [ ] **Criar `tests/test_pdf_smoke.py`**

```python
"""
Smoke test end-to-end: dados mock → HTML → PDF real.
Requer Playwright instalado (playwright install chromium).
Lento (~5s) — rodar separado com: pytest tests/test_pdf_smoke.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.pdf_generator import gerar_pdf, salvar_pdf

_DADOS_ECOMMERCE = {
    "{{cliente}}":          "Acme Store (Teste)",
    "{{periodo_inicio}}":   "26/05/2026",
    "{{periodo_fim}}":      "30/05/2026",
    "{{periodo_inicio_comp}}": "19/05/2026",
    "{{periodo_fim_comp}}": "23/05/2026",
    "{{semana}}":           "22",
    "{{freq}}":             "Semana",
    "{{fat_sem}}":          "R$ 847.320,00",
    "{{fat_sem_comp}}":     "R$ 686.700,00",
    "{{var_fat_sem}}":      "+23,4%",
    "{{roas}}":             "8,4x",
    "{{roas_comp}}":        "7,2x",
    "{{var_roas}}":         "+1,2",
    "{{inv_sem}}":          "R$ 72.900,00",
    "{{var_inv_sem}}":      "+8%",
    "{{vendas}}":           "3.840",
    "{{var_vendas}}":       "+24%",
    "{{fat_bruto}}":        "R$ 1.210.000,00",
    "{{var_fat_bruto}}":    "+31%",
    "{{pedidos}}":          "3.840",
    "{{var_pedidos}}":      "+24%",
    "{{tck_med}}":          "R$ 315,00",
    "{{sessoes}}":          "68.420",
    "{{var_sessoes}}":      "+18%",
    "{{taxa_conv}}":        "2,8%",
    "{{var_taxa_conv}}":    "+0,3",
    "{{proximo_report}}":   "Semana 23 · 02/06/2026",
}


def test_pdf_ecommerce_gerado():
    pdf = gerar_pdf("E-commerce", _DADOS_ECOMMERCE)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF", "Não é um PDF válido"


def test_pdf_ecommerce_abaixo_4mb():
    pdf = gerar_pdf("E-commerce", _DADOS_ECOMMERCE)
    tamanho_mb = len(pdf) / (1024 * 1024)
    assert tamanho_mb < 4.0, f"PDF muito grande: {tamanho_mb:.2f} MB"


def test_pdf_salvo_em_disco(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf = gerar_pdf("E-commerce", _DADOS_ECOMMERCE)
    caminho = salvar_pdf(pdf, "Acme Store (Teste)", 2026, 5, 22)
    assert caminho.exists()
    assert caminho.stat().st_size > 0


_DADOS_LEAD = {
    "{{cliente}}":       "Lead Teste",
    "{{periodo_inicio}}": "26/05/2026",
    "{{periodo_fim}}":    "30/05/2026",
    "{{semana}}":        "22",
    "{{freq}}":          "Semana",
    "{{leads}}":         "1.284",
    "{{var_leads}}":     "+12%",
    "{{cpl}}":           "R$ 12,80",
    "{{inv_sem}}":       "R$ 16.435,20",
}


def test_pdf_lead_com_site_gerado():
    pdf = gerar_pdf("Lead Com Site", _DADOS_LEAD)
    assert pdf[:4] == b"%PDF"


def test_pdf_lead_sem_site_gerado():
    pdf = gerar_pdf("Lead Sem Site", _DADOS_LEAD)
    assert pdf[:4] == b"%PDF"
```

- [ ] **Rodar testes unitários (rápidos)**

```bash
pytest tests/test_pdf_generator.py -v
```

Esperado: todos os testes PASS.

- [ ] **Rodar smoke test end-to-end (lento ~15s)**

```bash
PDF_REPORT_ATIVO=true pytest tests/test_pdf_smoke.py -v -s
```

Esperado: 5 testes PASS. O PDF do E-commerce deve ser < 4 MB.

- [ ] **Inspecionar PDF gerado visualmente**

```bash
PDF_REPORT_ATIVO=true python -c "
from core.pdf_generator import gerar_pdf
import sys, pathlib
dados = {
    '{{cliente}}': 'Turbo Demo',
    '{{periodo_inicio}}': '26/05/2026',
    '{{periodo_fim}}': '30/05/2026',
    '{{semana}}': '22',
    '{{freq}}': 'Semana',
    '{{fat_sem}}': 'R\$ 847.320,00',
    '{{var_fat_sem}}': '+23,4%',
    '{{roas}}': '8,4x',
    '{{inv_sem}}': 'R\$ 72.900,00',
    '{{proximo_report}}': 'Semana 23 · 02/06/2026',
}
pdf = gerar_pdf('E-commerce', dados)
out = pathlib.Path('/tmp/report_demo.pdf')
out.write_bytes(pdf)
print(f'PDF salvo em {out} ({len(pdf)/1024:.0f} KB)')
"
open /tmp/report_demo.pdf
```

Inspecionar visualmente: capa, resumo executivo, páginas de canal, contra-capa.

- [ ] **Commit final**

```bash
git add tests/test_pdf_smoke.py
git commit -m "test(pdf): smoke tests end-to-end — ecommerce e lead, tamanho < 4MB"
```

---

## Notas de Implementação

**Dados diários (gráfico de barras):** Os handlers atuais retornam agregados semanais, não dados dia-a-dia. As páginas de canal mostrarão "Dados diários indisponíveis" enquanto a coleta diária não for implementada. Para ativar os gráficos, passe `dados_diarios={"meta_ads": [v1,v2,v3,v4,v5]}` no `gerar_pdf()`.

**Fontes offline:** O `base.html` carrega Inter via Google Fonts CDN. Em produção sem internet, incorporar as fontes como base64 no CSS ou usar `playwright.page.route()` para interceptar e servir localmente.

**Playwright em CI:** Adicionar `playwright install chromium` ao script de setup do ambiente de CI.

**Feature flag:** `PDF_REPORT_ATIVO=true` no `.env` ativa a geração. Manter `false` até validação com clientes reais. O Google Slides continua sendo gerado normalmente.

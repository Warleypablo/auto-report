# Página de Insights de IA no Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ao PDF do report uma página de análise narrativa (3-5 parágrafos, PT-BR) gerada por Claude Sonnet 4.6 a partir dos números reais já coletados, sem nunca bloquear ou quebrar a geração.

**Architecture:** Novo módulo `core/ai_insights.py` desacoplado (recebe a API key, lazy-import do SDK `anthropic`, chamada à Claude isolada num helper mockável). `report_slides.py` (web backend) lê `settings.anthropic_api_key`, chama `gerar_analise`, injeta `{{ai_analise}}` no `dados`. Os templates renderizam uma página condicional após o Resumo Executivo.

**Tech Stack:** Python 3.12+, SDK `anthropic` (já em `web/backend/requirements.txt`, modelo `claude-sonnet-4-6`), Jinja2, pytest.

---

## Mapa de Arquivos

| Ação | Caminho | Responsabilidade |
|---|---|---|
| Create | `core/ai_insights.py` | `gerar_analise`, `_montar_resumo_factual`, `_validar_texto`, `_chamar_claude` |
| Create | `core/templates/partials/_ai_insights.html` | macro `ai_insights_page` |
| Modify | `core/templates/ecommerce.html` | página condicional + numeração |
| Modify | `core/templates/lead_com_site.html` | idem |
| Modify | `core/templates/lead_sem_site.html` | idem |
| Modify | `web/backend/services/report_slides.py` | chama `gerar_analise`, injeta placeholder |
| Create | `tests/test_ai_insights.py` | unit (Claude mockada) |

**Notas de contexto (confirmadas no código):**
- `anthropic>=0.40.0` já está em `web/backend/requirements.txt` e instalado no venv. NÃO está no Python do sistema — por isso o `import anthropic` é **lazy** (dentro de `_chamar_claude`), e os testes mockam `_chamar_claude` (não precisam do SDK).
- Padrão existente (`web/backend/api/turbomax.py:813,819-821`): `anthropic.Anthropic(api_key=...)` + `client.messages.create(model="claude-sonnet-4-6", max_tokens=..., system=..., messages=...)`. Resposta: `response.content[0].text`.
- A key vem de `app_settings.Settings.anthropic_api_key` (campo, default `""`). `core/` não importa `app_settings` (acoplamento) — recebe a key por parâmetro, com fallback para `os.environ["ANTHROPIC_API_KEY"]`.
- `dados` no ponto de injeção tem chaves no formato `{{...}}` (cru). Injetamos `dados["{{ai_analise}}"]`; o `pdf_generator.normalizar_dados` lowercaseia para `ai_analise`, que o template usa.

---

## Task 1: `_validar_texto` e `_montar_resumo_factual`

**Files:**
- Create: `core/ai_insights.py`
- Create: `tests/test_ai_insights.py`

- [ ] **Step 1: Escrever os testes (falham)**

Criar `tests/test_ai_insights.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


class TestValidarTexto:
    def test_texto_bom_passa(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto("A" * 600) is True

    def test_vazio_falha(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto("") is False
        assert _validar_texto("   ") is False

    def test_curto_demais_falha(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto("Curto.") is False

    def test_longo_demais_falha(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto("A" * 2500) is False

    def test_none_falha(self):
        from core.ai_insights import _validar_texto
        assert _validar_texto(None) is False


class TestMontarResumoFactual:
    def test_inclui_so_numeros_presentes(self):
        from core.ai_insights import _montar_resumo_factual
        dados = {
            "{{fat_face}}": "R$ 23.575", "{{roas_face}}": "8,4",
            "{{inv_face}}": "R$ 221", "{{var_fat_face}}": "+51,7%",
            "{{fat_goog}}": "-", "{{roas_goog}}": "—",   # google sem dados
        }
        ctx = {"cliente": "Piknik", "categoria": "E-commerce", "freq": "Semanal", "periodo": "26/05 a 30/05/2026"}
        resumo = _montar_resumo_factual(dados, ctx)
        assert "Piknik" in resumo
        assert "23.575" in resumo
        assert "8,4" in resumo
        assert "Meta Ads" in resumo
        # google sem dados → marcado como sem dados, sem valores
        assert "sem dados" in resumo.lower()

    def test_nao_inventa_valor_ausente(self):
        from core.ai_insights import _montar_resumo_factual
        dados = {"{{fat_face}}": "R$ 100"}
        ctx = {"cliente": "X", "categoria": "E-commerce", "freq": "Semanal", "periodo": "p"}
        resumo = _montar_resumo_factual(dados, ctx)
        # nenhum número fabricado além do fornecido
        import re
        nums = re.findall(r"\d[\d.,]*", resumo)
        assert "100" in resumo
```

- [ ] **Step 2: Rodar — confirmar FAIL**

```bash
cd /Users/mac0267/Documents/auto-report-main
python3 -m pytest tests/test_ai_insights.py -v 2>&1 | head -20
```
Esperado: `ModuleNotFoundError: No module named 'core.ai_insights'`

- [ ] **Step 3: Implementar `core/ai_insights.py` (parte 1)**

```python
"""
core/ai_insights.py

Gera a narrativa executiva do report (3-5 parágrafos, PT-BR) via Claude.
Desacoplado: recebe a API key por parâmetro (fallback p/ env). O SDK anthropic
é importado de forma lazy dentro de _chamar_claude — a chamada fica isolada e
mockável nos testes (sem precisar do SDK instalado).
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger(__name__)

_MODELO = "claude-sonnet-4-6"
_MIN_CHARS = 400
_MAX_CHARS = 2000

# Canais e as chaves de cada um (formato {{...}} cru, como vem do handler).
# (rótulo, [(label_metrica, chave_valor, chave_variacao_ou_None), ...])
_CANAIS = [
    ("Meta Ads", [
        ("faturamento", "{{fat_face}}", "{{var_fat_face}}"),
        ("ROAS", "{{roas_face}}", "{{var_roas_face}}"),
        ("investimento", "{{inv_face}}", "{{var_inv_face}}"),
        ("vendas", "{{vendas_face}}", "{{var_vendas_face}}"),
        ("CPA", "{{cpa_face}}", "{{var_cpa_face}}"),
    ]),
    ("Google Ads", [
        ("faturamento", "{{fat_goog}}", "{{var_fat_goog}}"),
        ("ROAS", "{{roas_goog}}", "{{var_roas_goog}}"),
        ("investimento", "{{inv_goog}}", "{{var_inv_goog}}"),
    ]),
    ("GA4", [
        ("sessões", "{{ses_ga}}", "{{var_ses_ga}}"),
        ("sessões (lead)", "{{ses}}", "{{var_ses}}"),
    ]),
    ("Painel de Negócio", [
        ("faturamento", "{{fat_sem}}", "{{var_fat_sem}}"),
        ("vendas", "{{vendas}}", "{{var_vendas}}"),
        ("leads", "{{lead_sem}}", "{{var_lead_sem}}"),
        ("CPL", "{{cpl}}", "{{var_cpl}}"),
        ("ticket médio", "{{tck_med}}", "{{var_tck_med}}"),
    ]),
]

_VAZIO = {"", "-", "—", "__NO_IMAGE__", None}


def _tem(v) -> bool:
    return v not in _VAZIO


def _validar_texto(texto) -> bool:
    """True se o texto tem tamanho razoável (não-vazio, entre _MIN e _MAX chars)."""
    if not isinstance(texto, str):
        return False
    n = len(texto.strip())
    return _MIN_CHARS <= n <= _MAX_CHARS


def _montar_resumo_factual(dados: dict, contexto: dict) -> str:
    """Monta um resumo estruturado e factual (só números reais) para a IA."""
    linhas = [
        f"Cliente: {contexto.get('cliente', '?')} ({contexto.get('categoria', '?')})",
        f"Período: {contexto.get('freq', '')} · {contexto.get('periodo', '')} (vs. período anterior)",
        "",
    ]
    for rotulo, metricas in _CANAIS:
        partes = []
        for label, chave_v, chave_var in metricas:
            v = dados.get(chave_v)
            if not _tem(v):
                continue
            var = dados.get(chave_var) if chave_var else None
            partes.append(f"{label} {v}" + (f" ({var})" if _tem(var) else ""))
        if partes:
            linhas.append(f"{rotulo}: " + " · ".join(partes))
        else:
            linhas.append(f"{rotulo}: sem dados no período")

    # Top criativos (Meta) — só os reais
    cria = []
    for i in range(1, 6):
        nome = dados.get(f"{{{{nome_adf{i}}}}}")
        if not _tem(nome):
            continue
        roas = dados.get(f"{{{{roas_adf{i}}}}}", "")
        conv = dados.get(f"{{{{conv_adf{i}}}}}", "")
        fat = dados.get(f"{{{{fat_adf{i}}}}}", "")
        cria.append(f'  {len(cria)+1}) "{nome}" — ROAS {roas} · {conv} conversões · {fat} faturamento')
    if cria:
        linhas.append("")
        linhas.append("TOP CRIATIVOS (Meta):")
        linhas.extend(cria)

    return "\n".join(linhas)
```

- [ ] **Step 4: Rodar — confirmar PASS**

```bash
python3 -m pytest tests/test_ai_insights.py -v
```
Esperado: todos os testes de `TestValidarTexto` e `TestMontarResumoFactual` PASS.

- [ ] **Step 5: Commit**

```bash
git add core/ai_insights.py tests/test_ai_insights.py
git commit -m "feat(ai): ai_insights _montar_resumo_factual + _validar_texto + testes"
```

---

## Task 2: `gerar_analise` + `_chamar_claude` (mockável)

**Files:**
- Modify: `core/ai_insights.py`
- Modify: `tests/test_ai_insights.py`

- [ ] **Step 1: Escrever os testes (falham)**

Adicionar ao fim de `tests/test_ai_insights.py`:
```python
from unittest.mock import patch


_DADOS = {"{{fat_face}}": "R$ 23.575", "{{roas_face}}": "8,4", "{{inv_face}}": "R$ 221"}
_CTX = {"cliente": "Piknik", "categoria": "E-commerce", "freq": "Semanal", "periodo": "26/05 a 30/05/2026"}


class TestGerarAnalise:
    def test_sem_key_retorna_none(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from core.ai_insights import gerar_analise
        assert gerar_analise(_DADOS, _CTX, api_key="") is None

    def test_texto_valido_retorna_texto(self):
        from core import ai_insights
        bom = "A análise da semana. " * 30  # > 400 chars
        with patch.object(ai_insights, "_chamar_claude", return_value=bom):
            out = ai_insights.gerar_analise(_DADOS, _CTX, api_key="sk-test")
        assert out == bom.strip()

    def test_texto_invalido_retorna_none(self):
        from core import ai_insights
        with patch.object(ai_insights, "_chamar_claude", return_value="curto"):
            assert ai_insights.gerar_analise(_DADOS, _CTX, api_key="sk-test") is None

    def test_excecao_na_api_retorna_none(self):
        from core import ai_insights
        with patch.object(ai_insights, "_chamar_claude", side_effect=RuntimeError("api down")):
            assert ai_insights.gerar_analise(_DADOS, _CTX, api_key="sk-test") is None

    def test_usa_key_do_env_se_nao_passada(self, monkeypatch):
        from core import ai_insights
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
        bom = "Texto bom da análise. " * 30
        with patch.object(ai_insights, "_chamar_claude", return_value=bom) as m:
            ai_insights.gerar_analise(_DADOS, _CTX)
        # _chamar_claude recebeu a key do env
        assert m.call_args.args[1] == "sk-env" or m.call_args.kwargs.get("api_key") == "sk-env"
```

- [ ] **Step 2: Rodar — confirmar FAIL**

```bash
python3 -m pytest tests/test_ai_insights.py::TestGerarAnalise -v 2>&1 | head -20
```
Esperado: FAIL (`gerar_analise` / `_chamar_claude` não existem).

- [ ] **Step 3: Implementar `gerar_analise` + `_chamar_claude`**

Adicionar ao fim de `core/ai_insights.py`:
```python
_SYSTEM_PROMPT = (
    "Você é um gestor de performance/tráfego sênior da Turbo Partners escrevendo "
    "a análise de um relatório para o dono do negócio (cliente).\n\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Use APENAS os números fornecidos no resumo. NUNCA invente, estime ou crie "
    "valores que não estão na lista. Se um dado não foi dado, não cite número.\n"
    "2. Não comente canais marcados como 'sem dados no período'.\n"
    "3. Escreva de 3 a 5 parágrafos curtos, em português do Brasil, fluido e claro, "
    "com tom de negócio — sem jargão técnico desnecessário e SEM bullet points.\n"
    "4. Destaque o que mais importa: o que cresceu ou caiu, o canal/criativo que "
    "puxou o resultado, e o contexto frente ao período anterior.\n"
    "5. Não escreva saudação, título nem assinatura. Apenas a análise."
)


def _chamar_claude(resumo: str, api_key: str, *, modelo: str = _MODELO, timeout: int = 15) -> str:
    """Chama a Claude e devolve o texto. Import lazy do SDK (isolado p/ testes)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=modelo,
        max_tokens=1024,
        timeout=timeout,
        system=[{
            "type": "text",
            "text": _SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},  # cacheia o prompt fixo (lote barato)
        }],
        messages=[{"role": "user", "content": resumo}],
    )
    return resp.content[0].text


def gerar_analise(dados: dict, contexto: dict, api_key: str = "") -> str | None:
    """Narrativa executiva via Claude. Retorna o texto PT-BR ou None em falha/
    timeout/texto inválido (o report segue sem a página)."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None
    try:
        resumo = _montar_resumo_factual(dados, contexto)
        texto = _chamar_claude(resumo, key).strip()
        return texto if _validar_texto(texto) else None
    except Exception:
        log.exception("Falha ao gerar análise de IA (%s)", contexto.get("cliente"))
        return None
```

- [ ] **Step 4: Rodar — confirmar PASS**

```bash
python3 -m pytest tests/test_ai_insights.py -v
```
Esperado: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add core/ai_insights.py tests/test_ai_insights.py
git commit -m "feat(ai): gerar_analise + _chamar_claude (Sonnet, prompt cacheado, fallback None)"
```

---

## Task 3: Partial `_ai_insights.html`

**Files:**
- Create: `core/templates/partials/_ai_insights.html`

- [ ] **Step 1: Criar o partial**

```html
{% macro ai_insights_page(texto, pagina, total_pags) %}
{% if texto %}
<div class="page">
  <div class="glow-tr"></div>
  <div class="section-eyebrow" style="margin-bottom:4px;">Análise da Semana</div>

  <div class="fill" style="justify-content:flex-start;">
    <div style="font-size:13px;line-height:1.85;color:var(--t-secondary);max-width:62ch;">
      {% for paragrafo in texto.split("\n") if paragrafo.strip() %}
      <p style="margin-bottom:14px;">{{ paragrafo.strip() }}</p>
      {% endfor %}
    </div>
  </div>

  <div style="display:flex;align-items:center;gap:8px;margin-top:8px;margin-bottom:10px;">
    <div style="width:5px;height:5px;border-radius:50%;background:linear-gradient(135deg,var(--cyan),var(--purple));"></div>
    <span style="font-size:8px;color:var(--t-ghost);letter-spacing:1.5px;text-transform:uppercase;">Gerado por IA · Turbo Partners</span>
  </div>

  <div class="page-footer">
    <div class="page-footer-brand">Turbo Partners</div>
    <div class="page-footer-num">{{ pagina }} / {{ total_pags }}</div>
  </div>
</div>
{% endif %}
{% endmacro %}
```

- [ ] **Step 2: Commit**

```bash
git add core/templates/partials/_ai_insights.html
git commit -m "feat(ai): partial _ai_insights.html (página Análise da Semana)"
```

---

## Task 4: Integrar no `ecommerce.html` (página condicional + numeração)

**Files:**
- Modify: `core/templates/ecommerce.html`

- [ ] **Step 1: Importar o macro**

No topo do `ecommerce.html`, após os outros `{% from ... %}`, adicionar:
```html
{% from "partials/_ai_insights.html"    import ai_insights_page %}
```

- [ ] **Step 2: Adicionar a numeração da página de IA**

Localizar o bloco de numeração (`{% set ns = namespace(pag=2) %}` ... `{% set ns.pag_resumo = 2 %}`). Logo após a linha `{% set ns.pag_resumo = 2 %}`, inserir:
```html
{% if ai_analise is defined and ai_analise %}{% set ns.pag = ns.pag + 1 %}{% set ns.pag_ai = ns.pag %}{% endif %}
```

- [ ] **Step 3: Renderizar a página após o Resumo Executivo**

Localizar o fechamento da página de Resumo Executivo (a `</div>` logo após `{{ page_footer(ns.pag_resumo, total_pags) }}`). Imediatamente depois, inserir:
```html
{# ═══════════ ANÁLISE DE IA (condicional) ═══════════ #}
{% if ai_analise is defined and ai_analise %}
  {{ ai_insights_page(ai_analise, ns.pag_ai, total_pags) }}
{% endif %}
```

- [ ] **Step 4: Teste de render (com e sem análise)**

```bash
cd /Users/mac0267/Documents/auto-report-main
python3 -c "
from core.pdf_generator import renderizar_html
base = {'cliente':'Acme','periodo_inicio':'26/05','periodo_fim':'30/05','freq':'Semanal','fat_face':'R\$ 100','roas_face':'8,4','inv_face':'R\$ 10'}
# com análise
ctx = dict(base); ctx['ai_analise']='Primeiro parágrafo da análise.\n\nSegundo parágrafo com contexto.'
ctx['has_meta']=True
html = renderizar_html('E-commerce', ctx)
assert 'Análise da Semana' in html and 'Primeiro parágrafo' in html, 'página IA não renderizou'
assert 'Gerado por IA' in html
print('COM análise: OK')
# sem análise
ctx2 = dict(base); ctx2['has_meta']=True
html2 = renderizar_html('E-commerce', ctx2)
assert 'Análise da Semana' not in html2, 'página IA apareceu sem análise'
print('SEM análise: OK (página omitida)')
"
```
Esperado: `COM análise: OK` + `SEM análise: OK (página omitida)`

- [ ] **Step 5: Commit**

```bash
git add core/templates/ecommerce.html
git commit -m "feat(ai): página de análise condicional no ecommerce.html"
```

---

## Task 5: Integrar nos templates Lead

**Files:**
- Modify: `core/templates/lead_com_site.html`
- Modify: `core/templates/lead_sem_site.html`

- [ ] **Step 1: `lead_com_site.html` — importar macro**

No topo, após os outros `{% from %}`, adicionar:
```html
{% from "partials/_ai_insights.html"    import ai_insights_page %}
```

- [ ] **Step 2: `lead_com_site.html` — numeração**

Após `{% set ns.pag_resumo = 2 %}`, inserir:
```html
{% if ai_analise is defined and ai_analise %}{% set ns.pag = ns.pag + 1 %}{% set ns.pag_ai = ns.pag %}{% endif %}
```

- [ ] **Step 3: `lead_com_site.html` — render após o Resumo**

Após a `</div>` que fecha a página de Resumo Executivo (logo após `{{ page_footer(ns.pag_resumo, total_pags) }}`), inserir:
```html
{% if ai_analise is defined and ai_analise %}
  {{ ai_insights_page(ai_analise, ns.pag_ai, total_pags) }}
{% endif %}
```

- [ ] **Step 4: Repetir os passos 1-3 em `lead_sem_site.html`**

As mesmas três inserções (import do macro, numeração após `ns.pag_resumo = 2`, render após o Resumo) no arquivo `core/templates/lead_sem_site.html`.

- [ ] **Step 5: Teste de render dos dois Lead**

```bash
python3 -c "
from core.pdf_generator import renderizar_html
for cat in ['Lead Com Site','Lead Sem Site']:
    ctx = {'cliente':'Lead X','freq':'Semanal','lead_face':'120','cpl_face':'R\$ 16','inv_face':'R\$ 1.920','has_meta':True,'ai_analise':'Parágrafo um.\n\nParágrafo dois.'}
    html = renderizar_html(cat, ctx)
    assert 'Análise da Semana' in html and 'Parágrafo um' in html, cat+' falhou'
    print(cat, 'OK')
"
```
Esperado: `Lead Com Site OK` + `Lead Sem Site OK`

- [ ] **Step 6: Commit**

```bash
git add core/templates/lead_com_site.html core/templates/lead_sem_site.html
git commit -m "feat(ai): página de análise condicional nos templates Lead"
```

---

## Task 6: Integrar no fluxo do report (`report_slides.py`)

**Files:**
- Modify: `web/backend/services/report_slides.py`

- [ ] **Step 1: Localizar o ponto de injeção**

Em `gerar_slides`, localizar a linha:
```python
    dados.update(handler.coletar_dados(cliente, periodo_ref, periodo_comp))
```
A injeção da análise vem logo depois dela (antes do bloco do modo PDF).

- [ ] **Step 2: Adicionar a geração da análise**

Inserir imediatamente após `dados.update(handler.coletar_dados(...))`:
```python
    # Análise narrativa por IA (não bloqueia o report — None se falhar/sem key).
    try:
        from core import ai_insights
        from app_settings import get_settings as _get_settings
        _contexto_ia = {
            "cliente": cliente.nome,
            "categoria": cliente.categoria,
            "freq": "Semanal" if FREQ == "SEMANAL" else "Mensal",
            "periodo": f"{periodo_ref.inicio:%d/%m} a {periodo_ref.fim:%d/%m/%Y}",
        }
        _texto_ia = ai_insights.gerar_analise(
            dados, _contexto_ia, api_key=_get_settings().anthropic_api_key
        )
        if _texto_ia:
            dados["{{ai_analise}}"] = _texto_ia
    except Exception:
        _log.exception("Falha ao injetar análise de IA para %s", cliente.nome)
```

- [ ] **Step 3: Verificar import**

```bash
cd /Users/mac0267/Documents/auto-report-main/web/backend
source .venv/bin/activate
python -c "import services.report_slides; print('import OK')"
```
Esperado: `import OK`

- [ ] **Step 4: Smoke E2E (chamada real — requer ANTHROPIC_API_KEY no .env)**

> Se `ANTHROPIC_API_KEY` não estiver no `.env`, `gerar_analise` retorna None e a página não aparece (comportamento correto). Para testar a chamada real, garanta a key no `.env` antes de rodar.

```bash
cd /Users/mac0267/Documents/auto-report-main
PDF_REPORT_ATIVO=true python3 -c "
import sys, pathlib, datetime
sys.path.insert(0,'.'); sys.path.insert(0,'web/backend')
from dotenv import load_dotenv; load_dotenv('.env')
import os
from core import ai_insights
dados = {'{{fat_face}}':'R\$ 23.575','{{roas_face}}':'8,4','{{var_roas_face}}':'+1,2','{{inv_face}}':'R\$ 221','{{vendas_face}}':'92'}
ctx = {'cliente':'Piknik','categoria':'E-commerce','freq':'Semanal','periodo':'26/05 a 30/05/2026'}
txt = ai_insights.gerar_analise(dados, ctx, api_key=os.environ.get('ANTHROPIC_API_KEY',''))
print('--- ANÁLISE ---'); print(txt if txt else '(None — sem key ou falha)')
"
```
Esperado: ou a narrativa (se key presente), ou `(None — sem key ou falha)`.

- [ ] **Step 5: Rodar a suite de testes do módulo**

```bash
python3 -m pytest tests/test_ai_insights.py -v
```
Esperado: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add web/backend/services/report_slides.py
git commit -m "feat(ai): report_slides gera e injeta {{ai_analise}} no fluxo do PDF"
```

---

## Notas de Implementação

**Ativação:** a feature só produz a página quando `ANTHROPIC_API_KEY` está configurada (via `.env` → `app_settings.anthropic_api_key`). Sem key, `gerar_analise` retorna `None` e o report sai normal, sem a página. Adicionar `ANTHROPIC_API_KEY=sk-...` ao `.env` para ativar.

**Reinício do backend:** mudanças em `core/` exigem reiniciar o uvicorn (o `--reload` só observa `web/backend/`).

**Custo/latência:** ~5-7s e ~5-8 centavos por report (Sonnet 4.6). O `cache_control` no system prompt reduz o custo em lote.

**Anti-alucinação:** o guardrail vive em dois lugares — `_montar_resumo_factual` (só passa números reais) e o `_SYSTEM_PROMPT` (proíbe inventar). O smoke E2E deve conferir que os números citados batem com o `dados`.

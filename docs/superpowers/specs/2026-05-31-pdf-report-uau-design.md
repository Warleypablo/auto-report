# PDF Report "Efeito UAU" — Design Spec

**Data:** 2026-05-31  
**Status:** Aprovado  
**Autor:** Warleypablo + Claude

---

## 1. Objetivo

Substituir o modelo atual de relatório (Google Slides com placeholders) por um **PDF gerado programaticamente** com alto impacto visual, identidade Turbo Partners, e conteúdo autoexplicativo — enviado via WhatsApp para o grupo do cliente.

**Critérios de sucesso:**
- Cliente entende os resultados sem precisar de apresentação
- Arquivo < 4 MB (limite prático para WhatsApp)
- Geração em < 30 s por cliente
- Visual indistinguível de um PDF produzido no Figma

---

## 2. Stack Técnico

| Camada | Tecnologia | Papel |
|---|---|---|
| Orquestração | `report_generator.py` (existente) | Continua sendo o ponto de entrada |
| Template | **Jinja2** | Renderiza HTML com dados do cliente |
| Gráficos | **Chart.js** (embutido no HTML) | Barras e linhas diárias |
| PDF Export | **Playwright** (headless Chromium) | Renderiza HTML → PDF A4 |
| Fontes | **Inter** (Google Fonts, embutida) | Tipografia principal |
| Ícones | SVG inline | Ícones de canal (Meta, Google, GA4) |

**Dependências novas a instalar:**
```
playwright>=1.44
jinja2>=3.1  # provavelmente já existe
```

**Playwright setup:**
```bash
pip install playwright
playwright install chromium
```

---

## 3. Estrutura de Páginas

O report tem **7 páginas fixas** para a categoria E-commerce. Categorias Lead Com Site e Lead Sem Site removem a página de GA4 (pág. 5), totalizando 6 páginas.

### Pág. 1 — Capa

**Conteúdo:**
- Badge de categoria do cliente (E-commerce / Lead / etc.)
- Nome do cliente (grande, peso 900)
- Período de referência (ex: Semana 22 · 26/05 a 30/05/2026)
- 3 KPIs destaque consolidados (maiores métricas do cliente)
- Linha de acento lateral (gradiente ciano → roxo)
- Glow decorativo no canto superior direito
- Label "Turbo Partners" no canto superior direito

**Dados dinâmicos:** `{{CLIENTE}}`, `{{PERIODO_INICIO}}`, `{{PERIODO_FIM}}`, `{{SEMANA}}`, 3 KPIs definidos por categoria:

| Categoria | KPI 1 | KPI 2 | KPI 3 |
|---|---|---|---|
| E-commerce | Faturamento Atribuído | ROAS (Meta ou Google, maior) | Investimento Total |
| Lead Com Site | Leads Gerados | CPL Médio | Investimento Total |
| Lead Sem Site | Leads Gerados | CPL Médio | Investimento Total |

---

### Pág. 2 — Resumo Executivo

**Conteúdo:**
- Número principal em destaque máximo (faturamento atribuído total ou maior métrica)
- Grade 2×2 com os 4 KPIs consolidados mais importantes
- Bloco de narrativa textual automática (1–2 frases geradas por template Jinja2 com condicional de alta/baixa performance)
- Comparação período atual vs. anterior (badge verde/vermelho)

**Dados dinâmicos:** KPIs somados de todos os canais, delta vs. período anterior.

---

### Pág. 3 — Meta Ads

**Conteúdo:**
- Header com ícone + nome do canal + período
- 2 KPIs grandes (Faturamento Atribuído + ROAS, ou CPL + Leads para Lead)
- Grade 3×2 com KPIs secundários: Investimento, Cliques, CTR, CPM, CPC, Conversões
- Gráfico de barras diário (Seg–Sex) com Chart.js
- Footer com branding TP + número de página

**Dados dinâmicos:** todos os placeholders Meta Ads existentes no handler atual.

---

### Pág. 4 — Google Ads

Mesma estrutura da pág. 3.

**KPIs grandes:** Conversões/Receita + ROAS  
**KPIs secundários:** Investimento, Impressões, CTR, Cliques, CPC, CPA

---

### Pág. 5 — GA4 *(somente E-commerce)*

Mesma estrutura de canal.

**KPIs grandes:** Sessões + Taxa de Conversão  
**KPIs secundários:** Novos Usuários, Taxa de Rejeição, Duração Média, Páginas/Sessão, Receita GA4, Ticket Médio  
**Gráfico:** Sessões por canal de aquisição (barras horizontais)

---

### Pág. 6 (ou 5 para Lead) — Painel Interno

**Conteúdo:**
- Header com ícone de gráfico + "Painel" + "Negócio · Semana X"
- 2 KPIs grandes (por categoria):
  - E-commerce: Faturamento Bruto + Pedidos
  - Lead: Leads Recebidos + CPL do Painel
- Grade 3×2 (por categoria):
  - E-commerce: Ticket Médio, Fat. Atribuído, % Atribuição, Receita Novos, Receita Recorrentes, % Recorrência
  - Lead: Taxa de Conversão Lead→Cliente, Custo por Aquisição, Fat. Gerado por Lead (se disponível), Meta de Leads, % Meta Atingida, —
- Gráfico de barras diário

---

### Pág. 7 (ou 6) — Contra-capa

**Conteúdo:**
- Logotipo Turbo Partners (texto estilizado + tagline)
- Linha decorativa gradiente
- Contatos: e-mail, site, Instagram
- Card "Próximo report": data calculada automaticamente (próxima semana Seg–Sex)

---

## 4. Design System

### Paleta de Cores

| Token | Valor | Uso |
|---|---|---|
| `--bg-base` | `#060612` | Fundo de página |
| `--bg-card` | `#08081A` | Cards e seções |
| `--bg-card-2` | `#0C0C22` | Cards secundários |
| `--bg-card-3` | `#0F0F25` | Cards de destaque |
| `--border` | `#1a1a35` | Bordas de cards |
| `--border-subtle` | `#111130` | Bordas secundárias |
| `--cyan` | `#00C8FF` | Acento primário, badges, deltas positivos... |
| `--purple` | `#7B2FFF` | Acento secundário, gradientes |
| `--gradient` | `linear-gradient(135deg, #00C8FF, #7B2FFF)` | Linha de acento, barras, before |
| `--text-primary` | `#FFFFFF` | Valores principais |
| `--text-secondary` | `#E5E7EB` | Valores secundários |
| `--text-muted` | `#9CA3AF` | Labels e sublabels |
| `--text-faint` | `#4B5563` | Labels de KPI pequenos |
| `--text-ghost` | `#374151` | Textos decorativos/footer |
| `--text-dim` | `#1F2937` | Footer branding (quase invisível) |
| `--up` | `#10B981` | Delta positivo |
| `--down` | `#EF4444` | Delta negativo |

### Tipografia

- **Família:** Inter (Google Fonts, pesos 300–900)
- **Valores KPI grandes:** 22–32px, peso 900, letter-spacing -0.5px
- **Labels:** 8–10px, peso 600–700, letter-spacing 2px, uppercase
- **Narrativa:** 12–13px, peso 400, line-height 1.6
- **Nomes de seção:** 14px, peso 800

### Componentes Reutilizáveis (partials Jinja2)

| Partial | Descrição |
|---|---|
| `_big_kpi.html` | Card de KPI grande com barra gradiente no topo |
| `_small_kpi.html` | Card de KPI secundário 3×2 |
| `_channel_header.html` | Header de página de canal (ícone + nome + período) |
| `_bar_chart.html` | Gráfico de barras Chart.js com dados diários |
| `_page_footer.html` | Footer com branding + número de página |
| `_delta_badge.html` | Badge colorido de variação percentual |

### Ícones de Canal

Todos SVG inline (sem dependência de arquivo externo):
- Meta Ads: ícone "f" estilizado com gradiente azul
- Google Ads: "G" multicolor
- GA4: losango dourado
- Painel: ícone de gráfico em gradiente ciano→roxo

---

## 5. Pipeline de Geração

```
report_generator.py
  └── processar_cliente(cliente)
        ├── [existente] coleta dados + monta placeholders dict
        ├── [NOVO] gerar_pdf(cliente, placeholders, periodo)
        │     ├── selecionar_template(categoria)  → template Jinja2
        │     ├── renderizar_html(template, dados) → HTML string
        │     ├── Playwright.new_page()
        │     ├── page.set_content(html)
        │     ├── page.wait_for_function("chartsReady()")  ← aguarda Chart.js
        │     └── page.pdf(format="A4", print_background=True) → bytes
        └── [NOVO] salvar_pdf(bytes, cliente, periodo) → path local
```

**Integração com fluxo atual:**
- `gerar_pdf()` substitui `template_manager` + `slide_filler` para clientes com feature ativa
- O `dict` de placeholders existente é reaproveitado integralmente — zero reescrita de handlers
- PDF salvo em `reports/{CLIENTE}/{ANO}/{MES}/Report_{SEMANA}_{CLIENTE}.pdf`

---

## 6. Template HTML por Categoria

Três templates Jinja2 (espelham as categorias atuais):

| Arquivo | Categoria | Diferenças |
|---|---|---|
| `templates/ecommerce.html` | E-commerce | 7 págs; inclui GA4 |
| `templates/lead_com_site.html` | Lead Com Site | 6 págs; sem GA4 |
| `templates/lead_sem_site.html` | Lead Sem Site | 6 págs; sem GA4, KPIs de lead |

Os três herdam de `templates/base.html` com o design system completo.

---

## 7. Narrativa Automática (Resumo Executivo)

A narrativa é gerada por template Jinja2 com condicional simples:

```jinja2
{% if delta_faturamento > 0 %}
A semana {{ SEMANA }} foi a {{ "melhor" if delta_faturamento > 20 else "uma boa" }} semana
do período, com faturamento de {{ FATURAMENTO }} — crescimento de {{ delta_faturamento }}%
em relação à semana anterior.
{% else %}
A semana {{ SEMANA }} registrou faturamento de {{ FATURAMENTO }}, uma retração de
{{ delta_faturamento|abs }}% vs. semana anterior. As campanhas seguem em otimização.
{% endif %}
```

Sem IA generativa — sem latência, sem custo extra, sem alucinação.

---

## 8. Entrega e Output

- **Formato:** PDF/A, A4 retrato (210×297mm), 96dpi interno
- **Tamanho alvo:** < 4 MB (compatível com WhatsApp)
- **Otimização:** imagens comprimidas via Playwright `scale` option; Chart.js renderiza em canvas (leve)
- **Nomenclatura:** `Report_Sem{N}_{CLIENTE}_{ANO}.pdf`
- **Destino:** pasta local `reports/` + upload no Google Drive (mesmo mecanismo atual)
- **Google Slides:** mantido em paralelo até validação do PDF com clientes reais

---

## 9. Fora de Escopo

- Dashboard interativo / web app
- Geração via IA (LLM para texto)
- Modo de edição visual / WYSIWYG
- Suporte a outros formatos de saída (PPTX, DOCX)
- Envio automático no WhatsApp (fora do escopo técnico desta fase)

---

## 10. Estrutura de Arquivos Novos

```
core/
  pdf_generator.py          # gerar_pdf(), salvar_pdf(), Playwright wrapper
  templates/
    base.html               # design system + CSS + Chart.js CDN
    ecommerce.html          # extends base, 7 páginas
    lead_com_site.html      # extends base, 6 páginas
    lead_sem_site.html      # extends base, 6 páginas
    partials/
      _big_kpi.html
      _small_kpi.html
      _channel_header.html
      _bar_chart.html
      _page_footer.html
      _delta_badge.html
reports/                    # output dos PDFs gerados
```

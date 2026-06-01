# Página de Insights de IA no Report — Design Spec

**Data:** 2026-06-01
**Status:** Aprovado
**Autor:** Warleypablo + Claude

---

## 1. Objetivo

Adicionar ao PDF do report uma página de **análise narrativa gerada por IA** (Claude Sonnet 4.6): um resumo executivo de 3-5 parágrafos, em PT-BR, que conta a história do período em linguagem de gestor sênior para o dono do negócio — usando **exclusivamente** os números reais já coletados.

**Critérios de sucesso:**
- A narrativa usa só os números do `dados` (zero invenção de valores).
- A página entra/sai dinamicamente (não aparece se a IA falhar).
- Nunca bloqueia ou quebra a geração do report.
- Texto bem escrito, tom de negócio, sem jargão desnecessário.

---

## 2. Arquitetura

### Módulo novo: `core/ai_insights.py`

```python
def gerar_analise(dados: dict, contexto: dict) -> str | None:
    """Gera a narrativa executiva via Claude. Retorna o texto PT-BR ou None
    em caso de falha/timeout/texto inválido (report segue sem a página)."""
```

- **`dados`**: dict de placeholders já coletado (`{{fat_face}}`, `{{roas}}`, `{{var_fat_sem}}`, criativos `{{nome_adf1}}`..., etc.), com chaves no formato `{{...}}`.
- **`contexto`**: `{"cliente": str, "categoria": str, "freq": "Semanal"|"Mensal", "periodo": str}`.
- **Retorno**: string com a narrativa, ou `None`.

Funções auxiliares internas:
- `_montar_resumo_factual(dados, contexto) -> str` — transforma o `dados` num resumo estruturado e legível (só números reais, por canal) para alimentar a IA.
- `_validar_texto(texto) -> bool` — checa tamanho razoável (~400–2000 chars) e não-vazio.

### Integração no fluxo (`web/backend/services/report_slides.py`, modo PDF)

```python
dados.update(handler.coletar_dados(cliente, periodo_ref, periodo_comp))  # existente

# NOVO — análise de IA (não bloqueia o report)
contexto = {
    "cliente": cliente.nome,
    "categoria": cliente.categoria,
    "freq": "Semanal" if FREQ == "SEMANAL" else "Mensal",
    "periodo": f"{periodo_ref.inicio:%d/%m} a {periodo_ref.fim:%d/%m/%Y}",
}
texto = ai_insights.gerar_analise(dados, contexto)
if texto:
    dados["{{ai_analise}}"] = texto

# ... segue para gerar PDF (já existente)
```

A injeção acontece após o `coletar_dados` e antes de `_gerar_e_subir_pdf`.

### Render (templates)

- Novo partial: `core/templates/partials/_ai_insights.html` — macro `ai_insights_page(texto, pagina, total_pags)`.
- Chamada condicional nos 3 templates (`ecommerce.html`, `lead_com_site.html`, `lead_sem_site.html`), **logo após o Resumo Executivo**.
- A página só renderiza se `ai_analise` estiver definido. A numeração dinâmica de páginas (namespace `ns`) ganha mais um passo quando `ai_analise` existe.

### Dependência

- SDK `anthropic` (adicionar a `requirements.txt` se ausente).
- `ANTHROPIC_API_KEY` no `.env`. Se ausente → `gerar_analise` retorna `None` (página não aparece).
- Modelo: `claude-sonnet-4-6`.

---

## 3. Input para a IA e guardrail anti-alucinação

### Resumo factual (input)

`_montar_resumo_factual` produz algo como:

```
Cliente: Piknik (E-commerce)
Período: Semanal · 26/05 a 30/05/2026 (vs. período anterior)

META ADS:    faturamento R$ 23.575 (+51,7%) · ROAS 8,4 (+1,2) · investimento R$ 221 (−24,1%) · 92 vendas (+53,3%) · CPA R$ 2,40
GOOGLE ADS:  sem dados no período
GA4:         sem dados no período
PAINEL:      ticket médio R$ 256,25 · ROAS geral 8,4

TOP CRIATIVOS (Meta):
  1) "Campanha Verão" — ROAS 31,4 · 48 conversões · R$ 52.000 faturamento
  2) "Remarketing Premium" — ROAS 28,7 · 39 conversões · R$ 44.300
```

Apenas chaves com valor real entram (ignora `—`, `-`, `__NO_IMAGE__`, vazios). Canais sem dado aparecem como "sem dados no período" (a IA é instruída a não comentá-los).

### System prompt (cacheado)

Instruções fixas (→ prompt caching, barato em lote):
1. Papel: gestor de tráfego/performance sênior da Turbo Partners escrevendo para o dono do negócio.
2. **Use APENAS os números fornecidos. Nunca invente, estime ou crie valores que não estão na lista.**
3. Não comente canais marcados como "sem dados".
4. Formato: 3-5 parágrafos, PT-BR, fluido, tom de negócio, sem jargão técnico desnecessário, sem bullet points.
5. Sem saudação, sem assinatura, sem título — apenas a análise (o título "Análise da Semana" é do template).
6. Destaque o que mais importa: o que cresceu/caiu, o canal/criativo que puxou o resultado, o contexto vs. período anterior.

### User prompt

O resumo factual + o contexto do cliente/período.

### Validação pós-geração

`_validar_texto`: não-vazio e entre ~400 e ~2000 caracteres. Fora disso → `None` (descarta).

---

## 4. Página, posição e erro

### Posição

Logo após o **Resumo Executivo** (pág. 3 quando presente). Sequência: números consolidados → narrativa da IA → canais em detalhe.

### Template (`_ai_insights.html`)

- Identidade dark (base.html): eyebrow "Análise da Semana" em ciano (`.section-eyebrow`).
- Narrativa em Inter ~13px, `line-height` ~1.8, cor `--t-secondary`, parágrafos espaçados, dentro de um container que preenche a página (`.fill`).
- Selo discreto no rodapé: "Gerado por IA · Turbo Partners" (transparência).
- Página limpa, sem cards.
- Footer padrão com numeração.

### Tratamento de erro (nunca bloqueia)

`gerar_analise` retorna `None` quando:
- `ANTHROPIC_API_KEY` ausente.
- Erro/timeout da API (cap ~15s).
- Texto inválido na validação.

Tudo em try/except com log. Com `None`, a página simplesmente não aparece e o report sai completo.

---

## 5. Testes

- **Unit `gerar_analise` (API mockada)**: retorna o texto quando a API responde; retorna `None` em exceção, em key ausente, e em texto inválido (muito curto/longo/vazio).
- **Unit `_montar_resumo_factual`**: o resumo contém só os números presentes no `dados` (canais sem dado viram "sem dados"); nenhum número inventado.
- **Unit render**: o template renderiza a página quando `ai_analise` existe e a omite quando não existe; numeração de páginas correta nos dois casos.
- **Smoke E2E (manual, 1 chamada real)**: gera um report com a página, inspeção visual + conferência de que os números citados batem com o `dados`.

---

## 6. Custo e latência

- ~5-7s adicionais por report (Sonnet 4.6).
- ~5-8 centavos por report; prompt caching reduz o custo em lote.
- Aceito conforme decisão (máxima qualidade priorizada sobre velocidade).

---

## 7. Fora de escopo

- Recomendações acionáveis / próximos passos (escolhido: só narrativa).
- Cards de destaque na página.
- Geração assíncrona / cache de insights entre execuções.
- Insights na aba web `/gestor/performance` (só no PDF do report).
- Tradução / multi-idioma.

---

## 8. Arquivos

```
core/
  ai_insights.py                       # NOVO — gerar_analise, _montar_resumo_factual, _validar_texto
  templates/
    partials/_ai_insights.html         # NOVO — macro ai_insights_page
    ecommerce.html                     # MOD — chamada condicional + numeração
    lead_com_site.html                 # MOD
    lead_sem_site.html                 # MOD
web/backend/
  services/report_slides.py            # MOD — chama gerar_analise, injeta {{ai_analise}}
requirements.txt                       # MOD — anthropic (se ausente)
tests/
  test_ai_insights.py                  # NOVO — unit (API mockada)
```

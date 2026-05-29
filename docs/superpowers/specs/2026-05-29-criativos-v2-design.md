# Design: Criativos v2 — camada de dados ad-level + página de criativos com filtros avançados

**Data:** 2026-05-29
**Branch:** main
**Status:** Aprovado (brainstorming)

---

## Problema

A página de criativos (`web/frontend/app/gestor/performance/page.tsx`, componente `RankingsPage`) hoje:

- Carrega **todos os clientes ativos** e dispara `metricasBreakdown(slug, mês)` **N×2 vezes** (mês atual + anterior), um request por cliente — não escala para a base inteira.
- Lê os criativos de **placeholders de texto** dentro de `Snapshot.raw_dados` (JSONB), com **teto rígido de 20 por rede** (`build_breakdown` itera `range(1, 21)` em `web/backend/services/metricas.py`) — embora a API da Meta colete até 5000.
- Trabalha por **mês fechado** — não há dado diário nem range de datas arbitrário.
- Não tem filtros de **faixa de faturamento**, **faixa de investimento** nem **tipo de cliente (lead/ecom)**.
- Google é coletado **só em nível de campanha** (sem anúncio, sem thumbnail, sem link).
- Não há **link** do criativo em lugar nenhum (ETL → API → front).
- A **thumbnail** existe só para a Meta e referencia a URL da Graph API, que **expira** com o tempo (criativos antigos quebram).

Os 9 ajustes pedidos não são "tweaks de página": juntos (datas exatas + sem teto + paridade Google + thumb durável + link) exigem **reconstruir a camada de dados de criativos**.

---

## Decisões fechadas (brainstorming)

| # | Tema | Decisão |
|---|------|---------|
| 8 | Limite de criativos | Lista **dinâmica, sem teto** (substitui os placeholders numerados) |
| 3 | Filtro de data | **Datas exatas (granularidade diária)** |
| — | Escopo Google | **Paridade total** com Meta (ad-level, diário, thumb, link) — limitada ao que a API do Google permite |
| 6 | Link do criativo | **Preview do anúncio** (Meta: `preview_shareable_link`; Google: deep-link para o Ads UI) |
| 5 | Thumbnail | **Rehospedar** a imagem (Postgres, ~320px, dedup por anúncio) |
| 1/2 | Faixas fat/inv | **Por criativo E por cliente** (dois conjuntos de filtros separados) |
| 7 | Filtro lead/ecom | **Chips das 3 categorias** (Ecom / Lead Com Site / Lead Sem Site) + atalho "Lead (ambos)" |
| 4 | Atualizar gestores | Re-sync ClickUp **sobrescrevendo** `cliente.gestor`; flag `gestor_travado` protege edição manual (default `false`) |
| 9 | Conectar base + Turbo | Todos os clientes ativos; **auditar IDs faltantes**; criar cliente "Turbo" |
| — | Janela de backfill | **Últimos 6 meses** no primeiro run |
| — | Storage da thumb | **Postgres** (sem infra nova); migração futura para GCS fica como saída registrada |

---

## Arquitetura

Aditiva: **não altera** `Snapshot` (mensal), que continua alimentando a geração de Slides e o dashboard do cliente. A página de criativos passa a ler das tabelas novas.

Abordagem escolhida: **modelo relacional fato + dimensão**. Rejeitada a alternativa de "manter JSONB de placeholders, só que diário" — não suporta range de datas arbitrário, filtro SQL por faixa, nem remoção do teto.

### Modelo de dados (3 tabelas novas, Postgres)

#### `criativos` (dimensão — metadados estáveis por anúncio)
| campo | tipo | detalhe |
|---|---|---|
| id | UUID | PK |
| cliente_id | UUID FK → clientes | |
| rede | Enum(`META`, `GOOGLE`) | |
| ad_id | String | id do anúncio na plataforma |
| nome | String | |
| tipo | String? | imagem / video / carrossel / search / display / pmax |
| preview_link | Text? | preview do anúncio (Meta) ou deep-link Ads UI (Google) |
| thumb_status | Enum(`pendente`, `ok`, `sem_imagem`, `erro`) | |
| primeiro_dia | Date | primeiro dia com dado coletado |
| ultimo_dia | Date | último dia com dado coletado |
| atualizado_em | timestamptz | |

`UNIQUE(cliente_id, rede, ad_id)`. Índices: `(cliente_id, rede)`.

#### `criativo_thumbs` (bytes da imagem — separada para não inchar a dimensão)
| campo | tipo | detalhe |
|---|---|---|
| criativo_id | UUID FK → criativos | PK |
| conteudo | BYTEA | imagem redimensionada (~320px no lado maior) |
| mime | String | ex.: `image/jpeg` |
| atualizado_em | timestamptz | |

#### `ad_insights` (fato — métrica por anúncio **por dia**)
| campo | tipo | detalhe |
|---|---|---|
| id | UUID | PK |
| cliente_id | UUID FK → clientes | |
| rede | Enum(`META`, `GOOGLE`) | |
| ad_id | String | |
| dia | Date | granularidade diária |
| investimento | Numeric(20,2) | spend do dia |
| faturamento | Numeric(20,2) | purchase/conversions value do dia |
| conversoes | Numeric(12,2) | Google pode ser fracionário |
| leads | Integer? | quando aplicável (categorias lead) |
| impressoes | BigInteger | |
| clicks | Integer | |
| video_3s | Integer? | para hook rate (só Meta) |

`UNIQUE(cliente_id, rede, ad_id, dia)`. Índices: `(cliente_id, dia)`, `(cliente_id, rede, dia)`.

**Métricas derivadas calculadas na agregação** (nunca armazenadas, para não dar inconsistência ao somar dias):
- ROAS = Σfaturamento / Σinvestimento
- CTR = Σclicks / Σimpressões
- CPA = Σinvestimento / Σconversões (ou Σleads para categorias lead)
- CPL = Σinvestimento / Σleads
- Hook rate = Σvideo_3s / Σimpressões (só Meta)
- Frequency = **não é somável**; será recalculada apenas se `reach` for coletado (Σimpressões / Σreach). Caso `reach` não seja coletado por dia, frequency fica `null` no agregado (decisão: não exibir frequency agregada incorreta). *(Refinar na implementação: avaliar incluir `reach` em `ad_insights`.)*

---

## ETL — coleta diária ad-level

Novo módulo `web/backend/etl/collect_criativos.py`, **separado** do snapshot mensal (`collect.py`).

- **Meta** (`core` reusa a lógica de `campaign_facebook_gather.py`):
  - `act_{id}/insights?level=ad&time_increment=1&fields=ad_id,ad_name,spend,impressions,clicks,reach,actions,action_values,video_3_sec_watched_actions&time_range={since,until}` → linhas diárias por anúncio.
  - Metadados/thumb/link em batch: `?ids={ad_ids}&fields=name,creative{thumbnail_url,image_url,object_type},preview_shareable_link` (lotes de 50).
  - Thumb: download da maior imagem disponível (`image_url` preferido a `thumbnail_url`) → resize ~320px → grava `criativo_thumbs.conteudo`.
- **Google** (estende `google_metrics_gather.py`):
  - GAQL em `ad_group_ad` com `segments.date`: `ad_group_ad.ad.id`, `ad_group_ad.ad.name`, `ad_group_ad.ad.type`, `metrics.cost_micros`, `metrics.conversions`, `metrics.conversions_value`, `metrics.impressions`, `metrics.clicks`.
  - Thumb via Asset API (`ad_group_ad.ad.image_ad` / responsive assets). **Search ads não têm imagem** → `thumb_status = sem_imagem`.
  - **Link**: Google não expõe `preview_shareable_link`; usar deep-link para o anúncio no Google Ads UI (ou `null` onde não construível).
- Upsert **idempotente** por `(cliente_id, rede, ad_id, dia)` em `ad_insights` e por `(cliente_id, rede, ad_id)` em `criativos`.
- Paralelização com `ThreadPoolExecutor` (alinhado à otimização de performance já feita no projeto), uma `SessionLocal` por thread.
- **Modos:**
  - **Backfill** (1º run / sob demanda): janela = últimos 6 meses.
  - **Incremental diário**: coleta o dia anterior + janela de retroação de ~3 dias (atribuição tardia reescreve os dias recentes).
- **Scheduling:** novo entrypoint `python -m etl.collect_criativos` (com flag `--backfill-meses N` / `--incremental`). Precisa de **cron diário** — hoje não há cron service no `render.yaml`; será adicionado (cron job no Render ou trigger externo via token, consistente com `ETL_TRIGGER_TOKEN`).

---

## Backend — API (`web/backend/api/gestor.py`)

### `GET /gestor/criativos` (novo, agregado — substitui o fetch N×2)
Query params:
- `de`, `ate` (YYYY-MM-DD) — range de datas exato.
- `rede` = `meta` | `google` | `todos`.
- `categoria` = lista (`ECOMMERCE`, `LEAD_COM_SITE`, `LEAD_SEM_SITE`).
- `gestor`, `cliente` (slug) — filtros existentes.
- `fat_min`, `fat_max`, `inv_min`, `inv_max` — faixa **por criativo** (aplicada via `HAVING` sobre o agregado do anúncio).
- `cli_fat_min`, `cli_fat_max`, `cli_inv_min`, `cli_inv_max` — faixa **por cliente** (agregado do cliente no range).
- `order_by` = `roas` | `faturamento` | `investimento` (default `roas`).
- `limit`, `offset` — paginação real.

Comportamento:
- Agrega `ad_insights` por `ad_id` no range (`GROUP BY`), junta com `criativos` (nome, thumb, link) e `clientes` (nome, categoria, gestor).
- Aplica filtros no banco; ordena; pagina. Resolve o "muito mais criativos do que os exibidos".
- Respeita acesso: admin vê tudo; gestor vê só seus clientes (join `usuario_clientes`).
- Resposta: criativos agregados com `thumb_url` (aponta para `/criativos/{id}/thumb`), `preview_link`, métricas do range (inv, fat, roas, ctr, cpa/cpl, impressões, conversões, hook_rate quando houver), `cliente_nome`, `cliente_slug`, `categoria`, `gestor_nome`. Inclui `total` (contagem) para a paginação.

### `GET /criativos/{criativo_id}/thumb` (novo)
Serve `criativo_thumbs.conteudo` com o `mime` correto, `Cache-Control` longo e `ETag`. 404 quando `thumb_status != ok`.

---

## Frontend — `app/gestor/performance/page.tsx`

- Substitui o fetch N×2 por **uma** chamada ao endpoint agregado, com **debounce** nos filtros.
- **Date range picker** (dia exato, de/até) + presets opcionais (últimos 30/60/90 dias, este mês, mês passado). Substitui o dropdown de mês único.
- **Chips de categoria** (Ecom / Lead Com Site / Lead Sem Site + atalho "Lead (ambos)").
- **Faixa de faturamento** e **faixa de investimento** via inputs min/max em R$, com toggle "por criativo" / "por cliente".
- Mantém pódio / tabela / scatter, agora sobre dados **paginados** (paginação ou infinite scroll).
- Thumb sempre via `/criativos/{id}/thumb` (rehospedada — não quebra). Link "Ver anúncio" abre `preview_link` em nova aba.
- Google passa a aparecer com thumb/link onde a plataforma permite; search ads exibem fallback (sem imagem).

---

## #4 — Atualizar gestores

- `web/backend/etl/sync_planilha.py` / endpoint de sync ClickUp passa a **atualizar** `cliente.gestor` quando o responsável mudou na fonte (hoje só preenche se `NULL`).
- Novo campo `clientes.gestor_travado` (Boolean, default `false`): quando `true`, o sync **não** sobrescreve (protege edição manual).
- Botão **"Atualizar gestores"** na UI dispara o sync.

---

## #9 — Auditoria de IDs + conectar base + Turbo

- Script/endpoint de **auditoria**: lista clientes ativos **sem** `id_meta_ads` e/ou `id_google_ads` → relatório (tela/CSV) para preenchimento na Planilha Central.
- Fluxo: preencher IDs na planilha → `sync_planilha` → backfill de criativos.
- Criar a row **"Turbo"** (a própria agência) na Planilha Central com os IDs de conta de anúncio da Turbo. **Operacional — depende de obter esses IDs.**

---

## Fases (cada uma é entregável; pode virar um PR)

- **F0 — Schema + auditoria:** migrations das 3 tabelas + `clientes.gestor_travado`; script de auditoria de IDs (#9 parte 1). Não quebra nada.
- **F1 — Coleta Meta:** ETL Meta ad-level diário + thumb rehospedada + preview link; backfill 6m.
- **F2 — Coleta Google:** ETL Google `ad_group_ad` diário + thumb (Asset API) + deep-link; limitações de plataforma.
- **F3 — API:** `GET /gestor/criativos` agregado + `GET /criativos/{id}/thumb`.
- **F4 — Frontend:** date range, chips de categoria, faixas (criativo/cliente), paginação, thumb/link, scatter sobre a nova fonte.
- **F5 — Gestores (#4):** re-sync com sobrescrita + `gestor_travado` + botão.
- **F6 — Conectar base + Turbo (#9 parte 2):** preencher IDs, sync, backfill, criar "Turbo".

Ordem sugerida: F0 → F1 → F3 → F4 (entrega valor com Meta) → F2 (Google) → F5 → F6. F2 pode rodar em paralelo a F3/F4.

---

## Fora de escopo (YAGNI)

- Migrar a geração de Slides para a nova fonte (snapshots mensais permanecem intactos).
- Distinção brand vs non-brand ROAS.
- Atribuição view-through / incrementality.
- Conversão de moeda (manter como hoje; sinalizar se a Meta retornar USD).
- Versionamento histórico de mudanças de criativo além do que `ad_insights` por dia já registra.

---

## Riscos e itens a confirmar na implementação

- **Google "100%" é limitado pela plataforma:** search ads não têm imagem; o Google não expõe um shareable preview link como a Meta → "link" para Google será deep-link para o Ads UI (ou `null`). Explicitar na UI.
- **Custo/rate-limit do backfill diário** (Meta e Google) — coletar em lotes com retry e paralelização controlada.
- **Moeda da Meta** pode vir em USD dependendo da conta — verificar e normalizar/sinalizar.
- **Cron no Render** para a coleta diária precisa ser criado (não existe hoje).
- **Crescimento das thumbs no Postgres** — monitorar; migração para GCS é a saída se necessário.
- **Frequency agregada** depende de coletar `reach` por dia — decidir na implementação se entra em `ad_insights`.
- **Reprocessamento de atribuição:** a janela de retroação (~3 dias) precisa reescrever (`upsert`) os dias já gravados sem duplicar.

# Sincronização de gestores via ClickUp — Design

**Data:** 2026-06-01
**Branch sugerida:** `fix/sync-gestores-cup-task-id`
**Escopo:** Backend (sync-gestores + automatch + encadeamento) com testes. **Não** altera a tela `clickup-vinculos`.

---

## Problema

O gestor exibido em vários clientes vem do **valor antigo cadastrado na planilha**, em vez do **responsável atual no ClickUp**. O sync existente não consegue sobrescrever.

### Causa raiz (confirmada empiricamente em produção)

O endpoint `POST /gestor/clientes/sync-gestores` (`web/backend/api/gestor.py:389`) relaciona cliente↔ClickUp por **nome exato normalizado** (`cn.nome_norm = cup.nome_norm`, linha 501) e **ignora o `cup_task_id`** — o vínculo confiável que todo o resto do código já usa (`list_clientes:592`, `list_gestores:673`, `cleanup-gestores:855`). Quando o nome no sistema diverge do nome no ClickUp, não casa → o sync não atualiza → o `gestor` fica congelado no valor inicial gravado pela planilha (`etl/sync_planilha.py:221`, só preenche quando `gestor IS NULL`).

### Números reais (banco de produção, 2026-06-01)

| Grupo | Qtd | Estado |
|---|---|---|
| Clientes ativos | 75 | |
| Vinculados (`cup_task_id IS NOT NULL`) | 51 | Corretos; **5** divergem só por **capitalização** (`Rayan coutinho`↔`Rayan Coutinho`, `Bruno Da Silva`↔`Bruno da Silva`) |
| Sem vínculo | 24 | Presos no valor da planilha; só **1** (Lavira) tem match exato no ClickUp |

Teste de proximidade (Python/difflib, read-only) nos 24 sem vínculo: ~15 têm match genuíno e forte (`AtriumVix`→`Atrium`, `Noway Drinks`→`Noway Drink`, `Medicinal da Web`→`Medicinal na Web`, `Zacca`→`Zacca Brasil`, `Lahza Foods`→`Lahza`, `Kaowz Facas`→`Kaowz`...). Um scoring ingênuo com "substring contains" produziu **falsos positivos graves** (`Fleur Brasil`→`UR`, `Nomã`→`Bueno Mate`, `Maves StreetWear`→`Areco`) — evidência direta de que auto-vincular fuzzy sem guardas geraria o "gestor errado" que queremos eliminar.

### Restrições de contexto

- `Cliente` **não** tem CNPJ → nome é o único sinal para o match cliente↔ClickUp.
- Banco: PostgreSQL. `pg_trgm` disponível mas **não instalado**. Volume pequeno (75 × 1130) → matching em memória (Python) é viável e já é o padrão do `automatch`.
- `staging.cup_contratos` tem: `id_task`, `id_subtask`, `servico`, `status`, `responsavel`, `data_inicio`, `data_encerramento`. Valores de `status`: `ativo` (450), `cancelado/inativo` (1005), `entregue` (480), `em cancelamento` (26), `pausado` (25), `onboarding` (17), `triagem` (14), `não usar` (2).

---

## Solução

Três partes, todas no backend.

### Parte 1 — `sync-gestores` passa a operar via `cup_task_id`

Reescrever `sync_gestores_from_clickup` para seguir o vínculo confiável, eliminando o re-match por nome.

**Caminho do dado (novo):**
```
clientes.cup_task_id  →  staging.cup_contratos.id_task
                         ↓ filtra servico ILIKE '%performance%'
                         ↓ escolhe melhor contrato (regra de vigência abaixo)
                         responsavel  →  normalize_gestor_name()  →  clientes.gestor
```

**Regra de escolha do contrato** (desempate, "vigente primeiro, depois mais recente"):
ordenar por prioridade de status e, dentro dela, `data_inicio DESC NULLS LAST`:
1. `ativo`
2. `onboarding`, `pausado`, `em cancelamento`
3. `entregue`
4. demais (`cancelado/inativo`, `triagem`, `não usar`, null)

**Gravação:**
- Aplica `normalize_gestor_name()` ao `responsavel` antes de gravar → corrige as 5 divergências cosméticas e mantém consistência com `gestores_cadastrados` (o dropdown em `list_gestores` casa por `c.gestor = gc.nome` exato).
- Respeita `gestor_travado = true` (não toca).
- Idempotente: só grava se `gestor` mudou (`IS DISTINCT FROM`).

**Decisão de escopo:** o sync opera **somente** sobre clientes com `cup_task_id`. Vincular é responsabilidade do `automatch` (Parte 2). Isso remove a duplicação de lógica de match e a fragilidade do match por nome dentro do sync. O encadeamento (Parte 3) garante a ordem.

**Implementação:** preferir SELECT dos pares `(cliente_id, gestor_atual, responsavel_bruto)` + normalização/decisão em Python + UPDATEs, em vez da CTE gigante atual. Mais testável e permite log de "de→para" por cliente.

**Resposta da API:** como o sync deixa de casar por nome, a métrica `com_match_nome` perde sentido e é **substituída** por `com_vinculo` (clientes com `cup_task_id`). Manter retrocompatível: incluir `com_vinculo` e manter `com_match_nome` como alias (= `com_vinculo`) por uma versão, para não quebrar consumidores. Demais chaves inalteradas: `atualizados`, `a_atualizar`, `total_ativos`, `com_contrato_performance`, `com_responsavel`.

### Parte 2 — Proximidade robusta no `automatch`

Substituir o match exato normalizado (`automatch_clickup`, `gestor.py:298`) por scoring de similaridade com guardas contra falso positivo.

**Scoring** (sobre nomes normalizados via `_normalize_nome` existente — remove acento, lowercase, sufixo jurídico, pontuação, colapsa espaços):
- Métrica base: `token_set_ratio` (rapidfuzz) normalizado para 0..1. Token-set já rejeita os falsos positivos do teste (`fleur brasil`×`ur`, `noma`×`bueno mate` não têm token em comum).
- **Guarda anti-substring:** não usar `partial_ratio`/"contains" cru para nomes curtos — foi a origem dos falsos positivos.
- **Guarda de token:** exigir ao menos um token significativo (len ≥ 4 após normalizar) compartilhado, OU score base muito alto sobre nome de token único (ex: `atriumvix`×`atrium`).
- **Margem:** auto-vínculo exige que o melhor candidato supere o 2º em margem mínima (ex: ≥ 0.08), evitando empates ambíguos.

**Dependência:** adicionar `rapidfuzz` a `web/backend/requirements.txt` (lib madura, wheels no deploy Render). Fallback aceitável: `difflib` (stdlib) se houver problema de deploy — decisão validada na implementação.

**Política de aplicação (conservadora, conforme decidido):**
- `score ≥ 0.90` **e** candidato único **e** margem ≥ 0.08 → **auto-vincula** (`matches`).
- `0.70 ≤ score < 0.90` ou múltiplos candidatos próximos → **sugestão** (`ambiguos`, com candidatos ranqueados top-5 por score) — revisão manual de 1 clique na tela existente.
- `score < 0.70` → `sem_candidato`.

**Contrato da resposta:** manter os campos que a tela `clickup-vinculos` consome (`matches[].cliente_nome/task_id/cup_nome`, `ambiguos[].cliente_nome/candidatos`, `sem_candidato`, `stats`). Adicionar `score` por item (aditivo, não quebra a tela). `dry_run=true` continua sendo o default.

### Parte 3 — Encadeamento

Novo endpoint `POST /gestor/clickup/sync-tudo` (ou reaproveitar fluxo) que executa em sequência:
1. `automatch(dry_run=false)` — aplica só os vínculos de alta confiança.
2. `sync_gestores_from_clickup()` — preenche o gestor dos clientes (agora) vinculados.

Retorna o consolidado: vínculos aplicados, sugestões pendentes (para revisão), gestores atualizados. Não auto-aplica nada de baixa confiança.

---

## Arquitetura / isolamento

Extrair a lógica de matching e de resolução de gestor para um módulo de serviço testável, separando-a dos handlers HTTP:

- `services/clickup_match.py`
  - `normalizar(nome) -> str` (reusa `_normalize_nome`)
  - `score(nome_a, nome_b) -> float`
  - `melhores_candidatos(cliente_nome, cup_rows, k=5) -> list[(score, task_id, nome)]`
  - `classificar(score, margem) -> 'auto' | 'sugestao' | 'sem_candidato'`
  - `responsavel_performance(contratos_do_task) -> str | None` (aplica a regra de vigência)

Os handlers em `api/gestor.py` passam a orquestrar; a lógica pura fica no serviço (entrada/saída claras, testável sem DB).

---

## Testes

Unit (lógica pura, sem DB), usando os **24 casos reais de produção como golden set**:
- `score()`: matches fortes pontuam alto (`Noway Drinks`/`Noway Drink`, `Zacca`/`Zacca Brasil`, `Lahza Foods`/`Lahza`, `AtriumVix`/`Atrium`, `Medicinal da Web`/`Medicinal na Web`).
- `score()`: lixo pontua baixo (`Fleur Brasil`/`UR`, `Nomã`/`Bueno Mate`, `Maves`/`Areco`, `Haux`/`Audax`, `Mineral Pro`/`MEATPRO`) — **nenhum** ≥ 0.90.
- `classificar()`: thresholds e margem corretos.
- `responsavel_performance()`: prefere `ativo` sobre `cancelado/inativo`; entre vigentes, mais recente por `data_inicio`; ignora contrato sem responsável.

Integração (DB de teste, estilo `test_sync_gestores.py` já existente):
- sync via `cup_task_id` atualiza gestor do vinculado e aplica `normalize_gestor_name` (corrige `Rayan coutinho`→`Rayan Coutinho`).
- `gestor_travado=true` não é tocado.
- cliente sem `cup_task_id` não é tocado pelo sync.
- `automatch` auto-aplica só ≥0.90 único; zona média vai para `ambiguos`.
- `sync-tudo` encadeia vínculo→gestor.

---

## Critérios de aceitação

1. Rodar `sync-tudo` em produção corrige as 5 divergências de capitalização dos vinculados.
2. ~14–16 dos 24 sem vínculo são vinculados automaticamente (score ≥ 0.90); o restante aparece como sugestão/sem-candidato para revisão.
3. Nenhum vínculo errado é auto-aplicado (golden set: zero falso positivo ≥ 0.90).
4. A tela `clickup-vinculos` continua funcionando sem alteração de código (contrato da API preservado).
5. Testes unit + integração passando.

---

## Riscos / pontos a validar na implementação

- **`rapidfuzz` no deploy Render** — validar instalação; fallback `difflib` se necessário.
- **Divergência frontend `ln`/`ln_id`** — `api-gestor.ts` chama `clickup/ln`, `clientes/ln`, `clientes/{id}/ln`, enquanto o backend expõe `clickup/automatch`, `clientes/sync-gestores`, `clientes/{id}/cup-task`. Investigar se há alias/rota faltante antes de assumir a tela funcional ponta-a-ponta.
- **Tuning do threshold** — calibrar 0.90/0.70/margem 0.08 contra o golden set; ajustar se algum match real ficar de fora ou algum lixo passar.
- **Clientes que não existem no ClickUp** (`Sim! Cerveja`, `Cosmobeauty`?) — permanecem sem vínculo; resolução é manual via busca (`/clickup/tasks`). Esperado, não é falha.

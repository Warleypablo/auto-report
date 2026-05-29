# F6 — Conectar toda a base + criar cliente "Turbo" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Conectar **toda** a base ativa à coleta de criativos: auditar quais clientes ativos estão sem `id_meta_ads`/`id_google_ads`, preencher os IDs na Planilha Central (ação humana), garantir por teste que `sync_clientes()` ingere novos clientes e back-preenche IDs que estavam `NULL`, criar a row **"Turbo"** (a própria agência) na planilha, rodar `sync_planilha` + backfill de 6 meses de `collect_criativos`, e validar o resultado na página `/gestor/performance`.

**Architecture:** Esta fase é majoritariamente **OPERACIONAL** (runbook). Cada passo é marcado como **[COMANDO]** (executável e verificável) ou **[AÇÃO HUMANA]** (edição manual na Planilha Central, fora do código). A única mudança de código é uma **garantia em TDD** sobre `web/backend/etl/sync_planilha.py::sync_clientes()`: ela deve (a) inserir clientes novos da planilha e (b) preencher `id_meta_ads`/`id_google_ads`/`id_ga4` quando o valor no DB ainda é `NULL` (preservando edições manuais já existentes). O comportamento atual do código (linhas 219‑232) já faz isso por design (cada `id_*` só é setado quando `existing.id_* is None`); a Task 1 trava esse contrato com teste antes de seguir o runbook, evitando que a F5 (que toca o mesmo arquivo para sobrescrever `gestor`) ou refactors futuros quebrem a ingestão de IDs.

**Pré-requisitos (devem estar mergeados antes desta fase):**
- **F0** — migration `add_criativos_ad_insights_gestor_travado` (down_revision `f79fffd5b218`) aplicada; tabelas `criativos`, `criativo_thumbs`, `ad_insights` e coluna `clientes.gestor_travado` existentes; script de auditoria de IDs entregue em `web/backend/scripts/audit_ids.py` (ver Task 2).
- **F1** — `web/backend/etl/collect_criativos.py` com `run_collect_criativos(backfill_meses=..., incremental=...)` (retorna `{"ok": int, "fail": int, "total": int}`, contrato §6.1) e o entrypoint CLI `python -m etl.collect_criativos --backfill-meses N` / `--incremental` (contrato §6.3).
- **F2** — coleta Google em `coletar_criativos_google` (contrato §6.1) — necessária para o backfill cobrir a rede Google.
- **F3/F4** — `GET /gestor/criativos` (contrato §4.1) e a página `/gestor/performance` consumindo a nova fonte (necessários para o passo de validação final).

> Se algum pré-requisito não estiver presente, **pare** e conclua a fase correspondente antes de executar este runbook.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x, FastAPI, Postgres, pytest + `unittest.mock`/`monkeypatch` (mock do `_fetch_values` do Google Sheets), CLI `python -m etl.collect_criativos`. Backend roda a partir de `web/backend/` (raiz do `sys.path` para `from db ...`, `from models ...`, `from etl ...`). Planilha Central via `core/leitura_central.py` (`CENTRAL_SHEET_URL` / `CENTRAL_TAB_NAME` em `config/settings.py`). Endpoint interno de sync: `POST /internal/sync-clientes` (router de `api/internal.py` montado com prefix `/internal` em `main.py`, header `x-etl-token` validado por `_require_token`).

---

## File Structure

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `web/backend/tests/test_sync_planilha.py` | **Create** | Trava em TDD o contrato de `sync_clientes()`: insere clientes novos e back-preenche IDs `NULL` sem sobrescrever IDs já preenchidos. Único código novo da fase. |
| `web/backend/etl/sync_planilha.py` | **Modify (só se a Task 1 falhar com `AttributeError`)** | Já implementa o contrato de upsert (linhas 219‑232). O único ajuste possível é promover `_fetch_values`/`parse_sheet_id` a import de topo para serem mockáveis. **Não** alterar a lógica de upsert nem o bloco do gestor (F5 é dona disso). |
| `web/backend/scripts/audit_ids.py` | **Read-only (consumir)** | Script de auditoria entregue na F0. F6 apenas o **roda**; não cria nem altera. |
| `web/backend/etl/collect_criativos.py` | **Read-only (consumir)** | ETL entregue na F1/F2. F6 apenas o **roda** em modo backfill. |
| Planilha Central (Google Sheets) | **AÇÃO HUMANA** | Preencher `ID META ADS` / `ID GOOGLE ADS` / `ID GA4` dos clientes faltantes e criar a row "Turbo". |

> **Convenção de colunas da Planilha Central** (de `core/leitura_central.py`, espelhada pelas constantes `COL_*` em `etl/sync_planilha.py`, normativa para as ações humanas):
> `CLIENTE`, `CATEGORIA`, `GESTOR`, `LINK PAINEL DE CONTROLE`, `LINK PASTA`, **`ID GOOGLE ADS`**, **`ID META ADS`**, **`ID GA4`**, `STATUS (AUTO)`, etc. Aba: `CENTRAL_TAB_NAME` (default `Automacao-Report`).
> **Atenção (normativo):** os labels de `CATEGORIA` na planilha são os **`.value` do enum `Categoria`**: `E-commerce`, `Lead Com Site`, `Lead Sem Site` (ver `web/backend/models/cliente.py`). `sync_clientes` faz `Categoria(categoria_str)` — a string tem de bater exatamente (com acento/maiúsculas), senão a linha é pulada com problema `categoria desconhecida`.

---

### Task 1: Travar em TDD o contrato de ingestão de `sync_clientes()` (insere novos + back-preenche IDs NULL)

Esta é a única tarefa de código. Garante que o passo "sync após preencher IDs" do runbook realmente importa novos clientes e popula IDs antes vazios — sem sobrescrever IDs que já foram preenchidos manualmente no DB.

**Files:**
- Create (test): `web/backend/tests/test_sync_planilha.py`
- Modify (somente se o teste falhar com `AttributeError`): `web/backend/etl/sync_planilha.py`

> **Pré-condição de ambiente:** estes testes usam `from db import SessionLocal`, ou seja, o **Postgres local de desenvolvimento** apontado por `DATABASE_URL` (banco `vitrine`), com o schema já migrado (F0 aplicada). Não usam `Base.metadata.create_all` — os testes do tipo "service/ETL via `SessionLocal`" seguem o padrão da fixture `cliente_id` de `tests/test_collect.py`.

Passos:

- [ ] **Escrever o teste que falha.** Criar `web/backend/tests/test_sync_planilha.py` com o conteúdo completo abaixo. O teste mocka `_fetch_values` (o mesmo símbolo que `sync_clientes` usa para ler a planilha) via `monkeypatch.setattr("etl.sync_planilha._fetch_values", ...)`, usa o `SessionLocal` real, e cria/limpa seus próprios clientes (padrão da fixture `cliente_id` de `tests/test_collect.py`). Cobre três casos do contrato F6: (1) cliente novo é inserido com os IDs da planilha; (2) cliente existente com IDs `NULL` recebe os IDs da planilha; (3) cliente existente com IDs **já preenchidos** NÃO é sobrescrito.

```python
import uuid

import pytest
from sqlalchemy import select

from db import SessionLocal
from etl.sync_planilha import sync_clientes
from models import Categoria, Cliente

# Cabeçalho exatamente como o esperado por sync_clientes (constantes COL_* de etl.sync_planilha,
# que casam com core.leitura_central). A ordem das colunas aqui define os índices que _row preenche.
HEADER = [
    "CLIENTE", "CATEGORIA", "GESTOR",
    "ID GOOGLE ADS", "ID META ADS", "ID GA4",
    "LINK PAINEL DE CONTROLE", "LINK PASTA",
    "PUBLICAR_VITRINE", "STATUS (AUTO)",
]


def _row(nome, categoria, gestor="", id_google="", id_meta="", id_ga4=""):
    # Mantém a mesma ordem de HEADER.
    return [nome, categoria, gestor, id_google, id_meta, id_ga4, "", "", "", ""]


@pytest.fixture
def limpar_slugs():
    """Registra slugs criados pelo teste e os remove no teardown."""
    criados: list[str] = []

    def _track(slug: str) -> str:
        criados.append(slug)
        return slug

    yield _track

    with SessionLocal() as s:
        for slug in criados:
            c = s.scalar(select(Cliente).where(Cliente.slug == slug))
            if c:
                s.delete(c)
        s.commit()


def test_sync_insere_cliente_novo_com_ids(limpar_slugs, monkeypatch):
    sufixo = uuid.uuid4().hex[:8]
    nome = f"Cliente Novo {sufixo}"
    slug = limpar_slugs(f"cliente-novo-{sufixo}")

    rows = [HEADER, _row(nome, "E-commerce", id_meta="act_111", id_google="555")]
    monkeypatch.setattr("etl.sync_planilha._fetch_values", lambda *a, **k: rows)

    resumo = sync_clientes()

    assert resumo["inserted"] >= 1
    with SessionLocal() as s:
        c = s.scalar(select(Cliente).where(Cliente.slug == slug))
    assert c is not None
    assert c.nome == nome
    assert c.categoria == Categoria.ECOMMERCE
    assert c.id_meta_ads == "act_111"
    assert c.id_google_ads == "555"


def test_sync_preenche_ids_nulos_de_cliente_existente(limpar_slugs, monkeypatch):
    sufixo = uuid.uuid4().hex[:8]
    nome = f"Cliente Sem IDs {sufixo}"
    slug = limpar_slugs(f"cliente-sem-ids-{sufixo}")

    # Cliente já existe no DB, porém com IDs NULL (caso típico pré-F6).
    with SessionLocal() as s:
        s.add(Cliente(
            slug=slug, nome=nome, categoria=Categoria.ECOMMERCE,
            id_meta_ads=None, id_google_ads=None, publicar_vitrine=False,
        ))
        s.commit()

    rows = [HEADER, _row(nome, "E-commerce", id_meta="act_222", id_google="666")]
    monkeypatch.setattr("etl.sync_planilha._fetch_values", lambda *a, **k: rows)

    sync_clientes()

    with SessionLocal() as s:
        c = s.scalar(select(Cliente).where(Cliente.slug == slug))
    assert c.id_meta_ads == "act_222"
    assert c.id_google_ads == "666"


def test_sync_nao_sobrescreve_ids_ja_preenchidos(limpar_slugs, monkeypatch):
    sufixo = uuid.uuid4().hex[:8]
    nome = f"Cliente Com IDs {sufixo}"
    slug = limpar_slugs(f"cliente-com-ids-{sufixo}")

    # Cliente já tem IDs preenchidos (edição manual a preservar).
    with SessionLocal() as s:
        s.add(Cliente(
            slug=slug, nome=nome, categoria=Categoria.ECOMMERCE,
            id_meta_ads="act_manual", id_google_ads="manual_google",
            publicar_vitrine=False,
        ))
        s.commit()

    # A planilha traz IDs DIFERENTES — não devem sobrescrever os do DB.
    rows = [HEADER, _row(nome, "E-commerce", id_meta="act_planilha", id_google="planilha")]
    monkeypatch.setattr("etl.sync_planilha._fetch_values", lambda *a, **k: rows)

    sync_clientes()

    with SessionLocal() as s:
        c = s.scalar(select(Cliente).where(Cliente.slug == slug))
    assert c.id_meta_ads == "act_manual"
    assert c.id_google_ads == "manual_google"
```

> **Nota sobre o mock:** hoje `sync_clientes()` faz `from core.leitura_central import _fetch_values, parse_sheet_id` **dentro** da função (import local, linha 130 de `etl/sync_planilha.py`). Quando o import é local, `_fetch_values` **não** é atributo do módulo `etl.sync_planilha`, então `monkeypatch.setattr("etl.sync_planilha._fetch_values", ...)` falha com `AttributeError`. O passo de implementação abaixo trata isso promovendo o import para o topo do módulo.

- [ ] **Rodar o teste e ver falhar.** A partir de `web/backend/`:
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_sync_planilha.py -v
  ```
  Saída esperada (FAIL): `AttributeError: <module 'etl.sync_planilha' ...> does not have the attribute '_fetch_values'` em todos os 3 testes (o `monkeypatch` não encontra o símbolo porque o import é local). Ir para o passo de implementação.
  > **Caso de contorno:** se, por já existir o símbolo no namespace de `etl.sync_planilha`, os 3 testes **passarem** sem nenhuma edição, registre que o contrato já é satisfeito, **pule o passo de implementação** e siga direto para o passo de regressão + commit (commitando apenas `tests/test_sync_planilha.py`).

- [ ] **Implementação mínima (apenas se o teste falhou com `AttributeError`).** Promover `_fetch_values` e `parse_sheet_id` para imports de topo em `web/backend/etl/sync_planilha.py`, tornando-os atributos do módulo (e portanto mockáveis). Aplicar exatamente estas duas edições, sem tocar na lógica de upsert (linhas 197‑255) nem no bloco do gestor (linha 221, propriedade da F5):

  **Edição A — adicionar import de topo.** Logo após a linha `from .cliente_publico import ClientePublico, slugify` (linha 22), inserir:
  ```python
  from core.leitura_central import _fetch_values, parse_sheet_id
  ```
  > `core/` já está garantido no `sys.path` pelo bloco `_ROOT = Path(__file__).resolve().parents[3]` (linhas 13‑16), então o import de topo resolve.

  **Edição B — remover a re-importação local** dentro de `sync_clientes()`. Trocar o bloco:
  ```python
      from config.settings import CENTRAL_SHEET_URL, CENTRAL_TAB_NAME
      from core.leitura_central import _fetch_values, parse_sheet_id
  ```
  por:
  ```python
      from config.settings import CENTRAL_SHEET_URL, CENTRAL_TAB_NAME
  ```
  (mantém o import local de `CENTRAL_SHEET_URL`/`CENTRAL_TAB_NAME`; remove só a linha de `_fetch_values, parse_sheet_id`, agora redundante).

  **Não** alterar o upsert: ele já preenche cada `id_*` somente quando `existing.id_* is None` (linhas 223‑228), que é exatamente o contrato. **Não** mexer na linha do gestor.

- [ ] **Rodar o teste e ver passar.**
  ```
  cd web/backend && .venv/bin/python -m pytest tests/test_sync_planilha.py -v
  ```
  Saída esperada (PASS): `3 passed`.

- [ ] **Rodar a regressão do ETL/sync** para garantir que promover o import não quebrou nada (o módulo `core.leitura_central` ainda é usado por `fetch_clientes_tolerante`, que faz seu próprio import local — confirmar que ambos coexistem):
  ```
  cd web/backend && .venv/bin/python -m pytest tests/ -k "sync or collect or internal" -v
  ```
  Saída esperada: todos `passed` (nenhum `error`/`failed`).

- [ ] **Commit.**
  ```
  git add web/backend/tests/test_sync_planilha.py web/backend/etl/sync_planilha.py
  git commit -m "$(cat <<'EOF'
test(etl): travar contrato de ingestão de sync_clientes (novos + back-fill de IDs NULL)

F6 depende de sync_planilha importar clientes novos e preencher
id_meta_ads/id_google_ads/id_ga4 quando ainda NULL, sem sobrescrever
IDs já preenchidos. Testa os 3 casos e promove _fetch_values a import
de topo para ser mockável.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
  ```

---

### Task 2: [COMANDO] Rodar a auditoria de IDs e gerar a lista de clientes ativos sem IDs

Usa o script de auditoria entregue na **F0** (`web/backend/scripts/audit_ids.py`, executável como módulo porque `web/backend/scripts/__init__.py` existe). F6 apenas o executa e captura o resultado.

**Files:** nenhum criado/modificado (consumo de artefato F0).

- [ ] **Confirmar que o script de auditoria existe** (entregue pela F0):
  ```
  cd web/backend && ls -1 scripts/audit_ids.py && echo ok
  ```
  Saída esperada: `scripts/audit_ids.py` seguido de `ok`. Se o arquivo **não** existir, **pare**: a F0 não foi concluída — finalize a parte 1 do #9 (script de auditoria) antes de prosseguir.

- [ ] **Rodar a auditoria** (a partir de `web/backend/`, com `DATABASE_URL` apontando para o banco de produção/staging alvo) e salvar o output para conferência:
  ```
  cd web/backend && .venv/bin/python -m scripts.audit_ids > /tmp/audit_ids_pre.txt; wc -l < /tmp/audit_ids_pre.txt
  ```
  Saída esperada: o arquivo `/tmp/audit_ids_pre.txt` com a lista (stdout/CSV) dos clientes `ativo == True` que têm `id_meta_ads IS NULL` e/ou `id_google_ads IS NULL`, e a contagem de linhas impressa por `wc -l`.

- [ ] **Verificação cruzada via SQL** (independe do formato exato do script — confirma o universo a preencher; usa os nomes de coluna reais do model `Cliente`). A partir de `web/backend/`:
  ```
  cd web/backend && .venv/bin/python -c "from db import SessionLocal; from sqlalchemy import select, or_; from models import Cliente; s=SessionLocal(); rows=s.scalars(select(Cliente).where(Cliente.ativo==True).where(or_(Cliente.id_meta_ads.is_(None), Cliente.id_google_ads.is_(None)))).all(); print('clientes_ativos_sem_id:', len(rows)); [print(c.slug, '|', c.nome, '| meta=', c.id_meta_ads, '| google=', c.id_google_ads) for c in rows]"
  ```
  Saída esperada: `clientes_ativos_sem_id: N` seguido da lista por slug. Esse `N` é a meta de preenchimento (Task 3). **Anotar o N** para conferir no fim (Task 5 deve reduzi-lo conforme os IDs forem preenchidos).

- [ ] **Checkpoint (sem commit — operacional).** A lista de `/tmp/audit_ids_pre.txt` é o input da próxima ação humana. Se a lista estiver **vazia** (`clientes_ativos_sem_id: 0`), todos os clientes já têm IDs → **pular a Task 3** e ir direto para a Task 4 (criação da Turbo).

---

### Task 3: [AÇÃO HUMANA] Preencher os IDs faltantes na Planilha Central

Edição manual na Planilha Central (Google Sheets). **Não é comando** — é trabalho humano com base na lista da Task 2.

**Files:** nenhum (edição na planilha externa).

- [ ] **Abrir a Planilha Central.** URL = valor de `CENTRAL_SHEET_URL` (`config/settings.py`; default `https://docs.google.com/spreadsheets/d/1dl3RTYvGRN4sXQjhracg0ysAfDpLl1y75iC9TIf5mEk/edit`), aba = `CENTRAL_TAB_NAME` (default `Automacao-Report`).

- [ ] **Para cada cliente da lista `/tmp/audit_ids_pre.txt`**, localizar a linha pelo nome (coluna `CLIENTE`) e preencher exatamente as células:
  - **`ID META ADS`** → o Ad Account ID da Meta no formato usado pelo gather (com prefixo `act_` quando aplicável, p.ex. `act_1234567890`).
  - **`ID GOOGLE ADS`** → o Customer ID do Google Ads (somente dígitos, sem hífens, p.ex. `5551234567`).
  - **`ID GA4`** → preencher se disponível (não bloqueia a coleta de criativos; é usado por outras telas).
  - **Não** alterar `CLIENTE` nem `CATEGORIA` desses clientes.

- [ ] **Deixar vazio quando não houver ID** (em vez de digitar `0`/`-`/`N/A`): `sync_clientes` aplica `_cell(...) or None`, tratando célula vazia como `None` e ignorando o campo; valores-lixo seriam ingeridos como IDs reais e quebrariam o ETL.

- [ ] **Registrar quais clientes/linhas foram preenchidos** (para conferência na Task 5). Marca de verificação: a lista da Task 2 está coberta, sem clientes ativos relevantes restando sem ID que deveriam tê-lo.

---

### Task 4: [AÇÃO HUMANA] Criar a row "Turbo" (a própria agência) na Planilha Central

Adiciona a Turbo como cliente, com os IDs de conta de anúncio da própria agência. **Operacional — depende de obter esses IDs internamente.**

**Files:** nenhum (edição na planilha externa).

- [ ] **Adicionar uma nova linha** na aba `Automacao-Report` com:
  - **`CLIENTE`** = `Turbo` (esse nome gera `slug = "turbo"` via `slugify`; conferir que não colide com slug existente — ver verificação na Task 5).
  - **`CATEGORIA`** = um dos labels `.value` do enum `Categoria` — **exatamente** `E-commerce`, `Lead Com Site` ou `Lead Sem Site` (grafia/acentuação idênticas às de `web/backend/models/cliente.py`). Escolher a que melhor representa a operação da própria Turbo (provável `Lead Com Site`).
  - **`ID META ADS`** = Ad Account ID da Turbo (formato `act_...`).
  - **`ID GOOGLE ADS`** = Customer ID do Google Ads da Turbo (só dígitos).
  - **`ID GA4`** = se houver.
  - **`GESTOR`** = responsável interno (opcional).

- [ ] **Conferir o valor da categoria** comparando com as linhas existentes da mesma categoria (mesma grafia/acentuação), para evitar `categoria desconhecida` no sync. Marca de verificação: a célula `CATEGORIA` da row "Turbo" é idêntica (string) à de outro cliente já sincronizado da mesma categoria.

---

### Task 5: [COMANDO] Rodar `sync_planilha` e confirmar a ingestão dos IDs e da Turbo

Roda o sync que ingere as edições das Tasks 3 e 4. Pode ser via Python (CLI) ou via o endpoint interno já existente (`POST /internal/sync-clientes`).

**Files:** nenhum (consumo de `etl/sync_planilha.py`).

- [ ] **Rodar o sync** (a partir de `web/backend/`, mesma `DATABASE_URL` da Task 2):
  ```
  cd web/backend && .venv/bin/python -c "from etl.sync_planilha import sync_clientes; import json; print(json.dumps(sync_clientes(), ensure_ascii=False, indent=2))"
  ```
  Saída esperada: JSON `{"inserted": ..., "updated": ..., "skipped": ..., "total": ..., "problemas": [...]}`. Conferir:
  - `inserted >= 1` (a row "Turbo" e quaisquer clientes novos da planilha).
  - `problemas` **não** contém `categoria desconhecida` para a Turbo (se contiver, voltar à Task 4 e corrigir a grafia da categoria).

  > **Alternativa via endpoint** (se preferir disparar pelo serviço rodando): `curl -s -X POST "$BASE_URL/internal/sync-clientes" -H "x-etl-token: $ETL_TRIGGER_TOKEN"` (rota montada com prefix `/internal` em `main.py`; header `x-etl-token` validado por `_require_token` em `api/internal.py`).

- [ ] **Confirmar que a Turbo foi criada com IDs:**
  ```
  cd web/backend && .venv/bin/python -c "from db import SessionLocal; from sqlalchemy import select; from models import Cliente; s=SessionLocal(); c=s.scalar(select(Cliente).where(Cliente.slug=='turbo')); print('turbo:', c and (c.nome, c.id_meta_ads, c.id_google_ads, c.ativo))"
  ```
  Saída esperada: tupla com `nome="Turbo"`, `id_meta_ads`/`id_google_ads` preenchidos, `ativo=True`. (Clientes novos são inseridos com `ativo=True` por padrão — linha 251 de `sync_planilha.py`.)

- [ ] **Re-rodar a auditoria** e confirmar que o número de ativos-sem-ID caiu para perto de zero (≤ os casos legítimos sem conta):
  ```
  cd web/backend && .venv/bin/python -m scripts.audit_ids > /tmp/audit_ids_pos.txt; echo "ANTES:"; wc -l < /tmp/audit_ids_pre.txt; echo "DEPOIS:"; wc -l < /tmp/audit_ids_pos.txt
  ```
  Saída esperada: `DEPOIS` < `ANTES`. Inspecionar `/tmp/audit_ids_pos.txt` — qualquer cliente remanescente deve ser um caso conhecido (cliente sem conta de anúncio na rede em questão).

---

### Task 6: [COMANDO] Rodar `collect_criativos` em modo backfill de 6 meses

Executa o ETL de criativos entregue na F1 (Meta) e F2 (Google) sobre toda a base agora conectada. **Janela: últimos 6 meses** (decisão do design, linha 38/119 do spec). Grava nas tabelas `criativos`, `criativo_thumbs` e `ad_insights` do contrato §1.

**Files:** nenhum (consumo de `etl/collect_criativos.py`).

- [ ] **Confirmar que o entrypoint existe** (entregue F1/F2):
  ```
  cd web/backend && .venv/bin/python -m etl.collect_criativos --help
  ```
  Saída esperada: ajuda do argparse listando as flags `--backfill-meses` e `--incremental` (mutuamente exclusivas, contrato §6.3). Se falhar, **pare**: F1/F2 não estão completas.

- [ ] **Smoke test com janela curta (1 mês) antes do backfill total** — valida credenciais/rate-limit/IDs num escopo reduzido:
  ```
  cd web/backend && .venv/bin/python -m etl.collect_criativos --backfill-meses 1
  ```
  Saída esperada: dict `{"ok": N, "fail": M, "total": T}` (contrato §6.1) com `fail` baixo. Investigar qualquer `fail` (token Meta/Google expirado, conta sem permissão, ID inválido) antes do backfill completo.

- [ ] **Rodar o backfill de 6 meses** sobre toda a base:
  ```
  cd web/backend && .venv/bin/python -m etl.collect_criativos --backfill-meses 6
  ```
  Saída esperada: dict `{"ok": <maioria>, "fail": <baixo>, "total": <todos os clientes ativos com ao menos um ID>}`. Este passo é longo (lotes + retry + `ThreadPoolExecutor`, conforme F1/F2).

- [ ] **Validar a gravação no banco** (tabelas e colunas exatas do contrato §1: `ad_insights`, `criativos`, coluna `dia`, enum `thumb_status` com valor `'ok'`):
  ```
  cd web/backend && .venv/bin/python -c "from db import SessionLocal; from sqlalchemy import text; s=SessionLocal(); print('ad_insights:', s.execute(text('SELECT count(*) FROM ad_insights')).scalar()); print('criativos:', s.execute(text('SELECT count(*) FROM criativos')).scalar()); print('thumbs_ok:', s.execute(text(\"SELECT count(*) FROM criativos WHERE thumb_status='ok'\")).scalar()); print('dia_min_max:', s.execute(text('SELECT min(dia), max(dia) FROM ad_insights')).first())"
  ```
  Saída esperada: `ad_insights` e `criativos` > 0; `dia_min` ~6 meses atrás e `dia_max` ~ontem; `thumbs_ok` > 0 (thumbs Meta rehospedadas).

- [ ] **Confirmar que a Turbo coletou criativos** (join `ad_insights` × `clientes` por `cliente_id`):
  ```
  cd web/backend && .venv/bin/python -c "from db import SessionLocal; from sqlalchemy import text; s=SessionLocal(); r=s.execute(text(\"SELECT count(*) FROM ad_insights i JOIN clientes c ON c.id=i.cliente_id WHERE c.slug='turbo'\")).scalar(); print('turbo_ad_insights:', r)"
  ```
  Saída esperada: `turbo_ad_insights > 0` (a agência aparece como cliente na coleta). Se `0`, revisar os IDs da Task 4 e re-rodar o backfill.

---

### Task 7: [COMANDO] Validar o resultado na página `/gestor/performance`

Validação end-to-end na UI (F3 API + F4 frontend), fechando o runbook.

**Files:** nenhum (validação manual/observacional).

- [ ] **Subir o stack local** (backend + frontend) conforme o procedimento do projeto, ou apontar para o ambiente onde o backfill rodou.

- [ ] **Testar a API agregada direto** (sanity antes da UI) — escolher um range dentro da janela de 6 meses. Os query params (`de`, `ate`, `rede`, `order_by`, `limit`) e o JSON de resposta seguem o contrato §4.1/§4.2:
  ```
  curl -s "$BASE_URL/api/gestor/criativos?de=2025-12-01&ate=2026-05-29&order_by=roas&limit=5" -H "Authorization: Bearer $TOKEN_GESTOR" | head -c 800; echo
  ```
  Saída esperada: JSON `{"items": [...], "total": <N>}`, cada item contendo os campos exatos do contrato §4.2 — `criativo_id`, `cliente_slug`, `cliente_nome`, `categoria`, `rede` (`"meta"`/`"google"`), `ad_id`, `roas` (`null` quando `investimento==0`), `thumb_url` (`/api/gestor/criativos/<criativo_id>/thumb` quando `thumb_status=="ok"`, senão `null`), `thumb_status`. `total` deve ser consistente com a contagem de `criativos` da Task 6.

- [ ] **Testar a rota de thumb** de um item com `thumb_status=="ok"` (contrato §4.4: `Cache-Control` longo, `ETag`, `media_type` = `mime`):
  ```
  curl -s -D - -o /dev/null "$BASE_URL/api/gestor/criativos/<criativo_id>/thumb" -H "Authorization: Bearer $TOKEN_GESTOR"
  ```
  Saída esperada: `HTTP/1.1 200`, `Content-Type: image/...`, `Cache-Control: public, max-age=31536000, immutable`, `ETag: "<criativo_id>"`.

- [ ] **Abrir `/gestor/performance` no navegador** e verificar:
  - Criativos aparecem com **thumbnails** (Meta) e/ou placeholder/`tipo` (Google search → `thumb_status="sem_imagem"`).
  - Filtros de **date range**, **chips de categoria** e **faixas (criativo/cliente)** retornam resultados.
  - A **Turbo** aparece quando filtrada por `cliente=turbo` (ou na lista geral, conforme escopo do usuário admin).
  - O **scatter** plota sobre a nova fonte (`CriativoAgregado`), sem erro de console.

- [ ] **Checklist final de fechamento da fase (verificável):**
  - [ ] `clientes ativos sem ID` reduzido ao mínimo conhecido (Task 5).
  - [ ] Row "Turbo" existe com IDs, `ativo=True` e `ad_insights` próprios (Tasks 5–6).
  - [ ] `ad_insights`/`criativos` populados na janela de 6 meses (Task 6).
  - [ ] `/gestor/performance` exibe os criativos da base completa, incluindo a Turbo (Task 7).
  - [ ] `tests/test_sync_planilha.py` verde (Task 1) garantindo que futuros syncs continuam ingerindo novos clientes/IDs.

> **Sem commit de código nesta task** (operacional). O único commit de código da fase é o da Task 1.

---

**Notas DRY/YAGNI:**
- F6 **não cria** scripts novos de auditoria nem de coleta — reusa `scripts/audit_ids.py` (F0) e `etl/collect_criativos.py` (F1/F2). O único código é o teste-guarda da Task 1 (+ possível promoção de import).
- A sobrescrita de `cliente.gestor` e o `gestor_travado` são responsabilidade da **F5**; este plano não os toca (apenas promove o import de `_fetch_values`/`parse_sheet_id` se necessário, sem mexer na lógica de upsert nem no bloco do gestor).
- O cron diário de `collect_criativos` no Render é item operacional do design (spec linha 121/206) e está **fora** deste contrato de código (mencionado nos pré-requisitos, não implementado aqui).

**Arquivos absolutos relevantes:**
- `/Users/mac0267/Documents/auto-report-main/web/backend/tests/test_sync_planilha.py` (criar)
- `/Users/mac0267/Documents/auto-report-main/web/backend/etl/sync_planilha.py` (ajuste condicional de import — só se a Task 1 falhar com `AttributeError`)
- `/Users/mac0267/Documents/auto-report-main/web/backend/scripts/audit_ids.py` (consumir, F0)
- `/Users/mac0267/Documents/auto-report-main/web/backend/etl/collect_criativos.py` (consumir, F1/F2)
- `/Users/mac0267/Documents/auto-report-main/web/backend/api/internal.py` (endpoint `POST /internal/sync-clientes`, header `x-etl-token`)
- `/Users/mac0267/Documents/auto-report-main/web/backend/api/gestor.py` (`GET /gestor/criativos`, `GET /gestor/criativos/{criativo_id}/thumb` — consumir na validação, F3)
- `/Users/mac0267/Documents/auto-report-main/web/frontend/app/gestor/performance/page.tsx` (validar na UI, F4)

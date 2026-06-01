# Sincronização de gestores via ClickUp — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o gestor dos clientes vir do responsável do contrato de Performance no ClickUp (via `cup_task_id`), e vincular automaticamente, por proximidade de nome, clientes que ainda não têm vínculo — sem auto-aplicar matches duvidosos.

**Architecture:** Lógica pura de matching e resolução de gestor isolada em `services/clickup_match.py` (testável sem DB). Os handlers em `api/gestor.py` orquestram: `sync-gestores` segue `cup_task_id`→contrato Performance vigente→`responsavel` normalizado; `automatch` usa proximidade robusta com guardas anti-falso-positivo, auto-aplicando só score ≥ 0.90 sem ambiguidade; `sync-tudo` encadeia vínculo→gestor. Contrato das APIs preservado para não quebrar a tela `clickup-vinculos`.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy 2 (psycopg3), PostgreSQL, rapidfuzz, pytest.

Spec: `docs/superpowers/specs/2026-06-01-sync-gestores-clickup-design.md`

---

## File Structure

- **Create** `web/backend/services/clickup_match.py` — lógica pura: normalização, score de proximidade, classificação (auto/sugestão/sem-candidato), melhores candidatos, resolução do responsável de Performance.
- **Create** `web/backend/tests/test_clickup_match.py` — testes unitários da lógica pura (golden set dos 24 casos reais).
- **Modify** `web/backend/requirements.txt` — adicionar `rapidfuzz`.
- **Modify** `web/backend/api/gestor.py` — reescrever `sync_gestores_from_clickup` (linhas 389-543) e `automatch_clickup` (linhas 298-381) para usar o serviço; mover `_normalize_nome`/`_SUFIXOS_JURIDICOS_RE` para o serviço; adicionar endpoint `sync-tudo`.
- **Modify** `web/backend/tests/test_sync_gestores.py` — atualizar fixture (colunas `id_task`, `status` em `cup_contratos`) e testes para o caminho via `cup_task_id`; adicionar testes de normalização e de automatch por proximidade.

---

## Task 1: Serviço de matching (lógica pura)

**Files:**
- Modify: `web/backend/requirements.txt`
- Create: `web/backend/services/clickup_match.py`
- Test: `web/backend/tests/test_clickup_match.py`

- [ ] **Step 1: Adicionar rapidfuzz às dependências**

Edite `web/backend/requirements.txt` e adicione, logo abaixo de `structlog>=24.4.0`:

```
rapidfuzz>=3.9.0
```

- [ ] **Step 2: Instalar a dependência**

Run: `cd web/backend && .venv/bin/pip install "rapidfuzz>=3.9.0"`
Expected: `Successfully installed rapidfuzz-...`

- [ ] **Step 3: Escrever os testes da lógica pura (golden set)**

Crie `web/backend/tests/test_clickup_match.py`:

```python
from datetime import date

from services.clickup_match import (
    normalizar,
    score,
    classificar,
    melhores_candidatos,
    responsavel_performance,
)


# ── normalizar ──────────────────────────────────────────────────────────
def test_normalizar_remove_acento_caixa_e_sufixo():
    assert normalizar("Tuá Cosméticos LTDA") == "tua cosmeticos"
    assert normalizar("  Loja   X  ") == "loja x"


# ── score: matches fortes devem passar de 0.90 ──────────────────────────
import pytest

MATCHES_FORTES = [
    ("Noway Drinks", "Noway Drink"),
    ("Zacca", "Zacca Brasil"),
    ("Lahza Foods", "Lahza"),
    ("AtriumVix", "Atrium"),
    ("Medicinal da Web", "Medicinal na Web"),
    ("Kaowz Facas", "Kaowz"),
    ("Lavira", "Lavira"),
]

@pytest.mark.parametrize("a,b", MATCHES_FORTES)
def test_score_match_forte_acima_de_090(a, b):
    assert score(a, b) >= 0.90, f"{a} ~ {b} = {score(a, b):.2f}"


# ── score: lixo NUNCA pode chegar a 0.90 (anti-falso-positivo) ──────────
LIXO = [
    ("Fleur Brasil", "UR"),
    ("Nomã", "Bueno Mate"),
    ("Maves StreetWear Ecommerce", "Areco"),
    ("Haux", "Audax"),
    ("Mineral Pro", "MEATPRO"),
    ("Sim! Cerveja", "MS Creative"),
    ("Cosmobeauty", "Beautyin"),
]

@pytest.mark.parametrize("a,b", LIXO)
def test_score_lixo_abaixo_de_090(a, b):
    assert score(a, b) < 0.90, f"{a} ~ {b} = {score(a, b):.2f}"


# ── classificar ─────────────────────────────────────────────────────────
def test_classificar_auto_quando_alto_e_unico():
    assert classificar([(0.95, "t1", "Noway Drink")]) == "auto"

def test_classificar_sugestao_quando_ambiguo():
    # dois candidatos altos e próximos -> margem insuficiente
    assert classificar([(0.95, "t1", "A"), (0.93, "t2", "B")]) == "sugestao"

def test_classificar_sugestao_quando_medio():
    assert classificar([(0.80, "t1", "A")]) == "sugestao"

def test_classificar_sem_candidato_quando_baixo():
    assert classificar([(0.40, "t1", "A")]) == "sem_candidato"
    assert classificar([]) == "sem_candidato"


# ── melhores_candidatos ─────────────────────────────────────────────────
def test_melhores_candidatos_ordena_por_score_desc():
    cup = [
        {"task_id": "t1", "nome": "Atrium"},
        {"task_id": "t2", "nome": "Padaria do Zé"},
        {"task_id": "t3", "nome": "Atrium Holding"},
    ]
    res = melhores_candidatos("AtriumVix", cup, k=2)
    assert len(res) == 2
    assert res[0][0] >= res[1][0]
    assert res[0][1] in {"t1", "t3"}


# ── responsavel_performance: vigência ───────────────────────────────────
def test_responsavel_prefere_contrato_ativo_sobre_cancelado():
    contratos = [
        {"servico": "Gestão de Performance", "status": "cancelado/inativo",
         "responsavel": "Antigo", "data_inicio": date(2026, 5, 1)},
        {"servico": "Gestão de Performance", "status": "ativo",
         "responsavel": "Atual", "data_inicio": date(2026, 1, 1)},
    ]
    assert responsavel_performance(contratos) == "Atual"

def test_responsavel_mais_recente_entre_vigentes():
    contratos = [
        {"servico": "Gestão de Performance", "status": "ativo",
         "responsavel": "Velho", "data_inicio": date(2025, 1, 1)},
        {"servico": "Gestão de Performance", "status": "ativo",
         "responsavel": "Novo", "data_inicio": date(2026, 1, 1)},
    ]
    assert responsavel_performance(contratos) == "Novo"

def test_responsavel_ignora_servico_nao_performance():
    contratos = [
        {"servico": "Consultoria", "status": "ativo",
         "responsavel": "X", "data_inicio": date(2026, 1, 1)},
    ]
    assert responsavel_performance(contratos) is None

def test_responsavel_ignora_responsavel_vazio():
    contratos = [
        {"servico": "Gestão de Performance", "status": "ativo",
         "responsavel": "   ", "data_inicio": date(2026, 1, 1)},
    ]
    assert responsavel_performance(contratos) is None
```

- [ ] **Step 4: Rodar os testes e verificar que falham**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_clickup_match.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'services.clickup_match'`

- [ ] **Step 5: Implementar o serviço**

Crie `web/backend/services/clickup_match.py`:

```python
from __future__ import annotations

import re
import unicodedata
from datetime import date as _date

from rapidfuzz import fuzz

# ── Normalização de nome (movida de api/gestor.py para reuso) ────────────
_SUFIXOS_JURIDICOS_RE = re.compile(
    r"\s+(ltda|me|mei|epp|eireli|s\.?a\.?|sa|inc\.?|corp\.?)\s*\.?\s*$",
    re.IGNORECASE,
)

# Tokens que não carregam identidade de marca — ignorados ao exigir
# "token significativo em comum" no guarda anti-falso-positivo.
_STOPWORDS = {
    "da", "de", "do", "das", "dos", "e",
    "ltda", "me", "mei", "epp", "eireli", "sa",
    "ecommerce", "ecomm", "whats", "whatsapp", "loja", "lojas",
}


def normalizar(s: str | None) -> str:
    """lower, sem acento, sem sufixo jurídico, sem pontuação, espaços colapsados."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.lower().strip()
    s = _SUFIXOS_JURIDICOS_RE.sub("", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens_sig(s: str) -> set[str]:
    return {t for t in s.split() if len(t) >= 4 and t not in _STOPWORDS}


def _ha_token_em_comum(ta: set[str], tb: set[str]) -> bool:
    """Evidência de que os nomes falam da mesma marca: token igual, prefixo
    forte (nomes colados/abreviados) ou par de tokens muito similar."""
    for a in ta:
        for b in tb:
            if a == b:
                return True
            if len(a) >= 5 and len(b) >= 5 and (a.startswith(b) or b.startswith(a)):
                return True
            if fuzz.ratio(a, b) / 100.0 >= 0.85:
                return True
    return False


def score(nome_a: str, nome_b: str) -> float:
    """Similaridade 0..1 entre dois nomes, com guarda anti-falso-positivo.

    Retorna 0.0 quando não há token significativo em comum — bloqueia casos
    como 'Fleur Brasil'×'UR' e 'Nomã'×'Bueno Mate' que enganam métricas de
    substring.
    """
    a, b = normalizar(nome_a), normalizar(nome_b)
    if not a or not b:
        return 0.0
    ta, tb = _tokens_sig(a), _tokens_sig(b)
    if not ta or not tb or not _ha_token_em_comum(ta, tb):
        return 0.0

    base = max(fuzz.token_set_ratio(a, b), fuzz.token_sort_ratio(a, b)) / 100.0

    # Boost para containment de prefixo (nomes colados/abreviados já validados
    # pelo guarda de token): 'atriumvix' contém 'atrium', 'zaccabrasil' contém
    # 'zacca'. Sem espaços, prefixo do lado mais curto (>=5 chars).
    aj, bj = a.replace(" ", ""), b.replace(" ", "")
    curto, longo = sorted([aj, bj], key=len)
    boost = 0.92 if (len(curto) >= 5 and longo.startswith(curto)) else 0.0

    return max(base, boost)


# Thresholds (calibráveis): auto-vínculo só com alta confiança e sem ambiguidade.
AUTO_MIN = 0.90
SUGESTAO_MIN = 0.70
MARGEM_MIN = 0.08


def classificar(candidatos: list[tuple[float, str, str]]) -> str:
    """Recebe candidatos já ordenados por score desc (score, task_id, nome).
    Retorna 'auto' | 'sugestao' | 'sem_candidato'."""
    if not candidatos or candidatos[0][0] < SUGESTAO_MIN:
        return "sem_candidato"
    melhor = candidatos[0][0]
    segundo = candidatos[1][0] if len(candidatos) > 1 else 0.0
    if melhor >= AUTO_MIN and (melhor - segundo) >= MARGEM_MIN:
        return "auto"
    return "sugestao"


def melhores_candidatos(
    nome_cliente: str,
    cup_rows: list[dict],
    k: int = 5,
) -> list[tuple[float, str, str]]:
    """Top-k (score, task_id, nome) de cup_rows (cada um {'task_id','nome'})."""
    ranked = [
        (score(nome_cliente, r["nome"]), r["task_id"], r["nome"])
        for r in cup_rows
        if r.get("nome")
    ]
    ranked.sort(key=lambda t: t[0], reverse=True)
    return ranked[:k]


# ── Resolução do responsável de Performance ──────────────────────────────
_STATUS_PRIORIDADE = {
    "ativo": 0,
    "onboarding": 1, "pausado": 1, "em cancelamento": 1,
    "entregue": 2,
}


def _status_rank(status: str | None) -> int:
    return _STATUS_PRIORIDADE.get((status or "").strip().lower(), 3)


def _data_key(d) -> _date:
    return d if isinstance(d, _date) else _date.min


def responsavel_performance(contratos: list[dict]) -> str | None:
    """Dado os contratos de um cliente (cada um {'servico','status',
    'responsavel','data_inicio'}), escolhe o contrato de Performance vigente
    mais recente e retorna o responsável (ou None)."""
    perf = [
        c for c in contratos
        if "performance" in (c.get("servico") or "").lower()
        and (c.get("responsavel") or "").strip()
    ]
    if not perf:
        return None
    # ordenação estável em dois passos: data desc, depois status asc domina
    perf.sort(key=lambda c: _data_key(c.get("data_inicio")), reverse=True)
    perf.sort(key=lambda c: _status_rank(c.get("status")))
    return perf[0]["responsavel"].strip()
```

- [ ] **Step 6: Rodar os testes e verificar que passam**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_clickup_match.py -q`
Expected: PASS (todos). Se algum match forte ficar < 0.90 ou algum lixo passar de 0.90, ajuste a implementação de `score`/`_ha_token_em_comum` (não os testes) até o golden set passar.

- [ ] **Step 7: Apontar `api/gestor.py` para a normalização do serviço (DRY)**

Em `web/backend/api/gestor.py`, remova a definição local de `_SUFIXOS_JURIDICOS_RE` (linhas ~277-280) e de `_normalize_nome` (linhas ~283-295) e, junto aos imports de serviço no topo (perto de `from services.criativos import agregar_criativos`), adicione:

```python
from services.clickup_match import normalizar as _normalize_nome
```

Mantenha o uso de `_normalize_nome(...)` onde já existe (o alias preserva o nome usado no arquivo).

- [ ] **Step 8: Rodar a suíte de gestor para garantir que nada quebrou ainda**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_clickup_match.py tests/test_sync_gestores.py -q`
Expected: `test_clickup_match.py` PASS; `test_sync_gestores.py` ainda pode falhar (será corrigido na Task 2) — confirme que a falha é só nelas e não em import.

- [ ] **Step 9: Commit**

```bash
cd /Users/mac0267/Documents/auto-report-main
git add web/backend/requirements.txt web/backend/services/clickup_match.py web/backend/tests/test_clickup_match.py web/backend/api/gestor.py
git commit -m "feat(gestores): serviço puro de matching ClickUp (proximidade + vigência)"
```

---

## Task 2: `sync-gestores` via `cup_task_id`

**Files:**
- Modify: `web/backend/api/gestor.py:389-543` (`sync_gestores_from_clickup`)
- Test: `web/backend/tests/test_sync_gestores.py`

- [ ] **Step 1: Atualizar o fixture e o seed do teste para o novo caminho**

Em `web/backend/tests/test_sync_gestores.py`, troque o `CREATE TABLE staging.cup_contratos` (linhas ~35-42) por uma versão com `id_task` e `status`:

```python
        conn.execute(text("""
            CREATE TABLE staging.cup_contratos (
                id_subtask text,
                id_task text,
                servico text,
                status text,
                responsavel text,
                data_inicio date
            )
        """))
```

E troque o INSERT do contrato dentro de `_seed_cliente` (linhas ~98-103) para popular `id_task` (= `task_id`) e `status`:

```python
        s.execute(
            text("INSERT INTO staging.cup_contratos "
                 "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                 "VALUES (:sub, :task, 'Gestão de Performance', 'ativo', :resp, :dt)"),
            {"sub": subtask_id, "task": task_id, "resp": "Novo Gestor",
             "dt": date(2026, 1, 1)},
        )
```

- [ ] **Step 2: Adicionar teste de normalização e de cliente sem vínculo**

Ainda em `test_sync_gestores.py`, adicione no fim do arquivo:

```python
def _seed_cliente_resp(TS, *, nome, gestor, task_id, resp, status="ativo",
                       data_inicio=date(2026, 1, 1), cup_task_id=None):
    """Cliente + contrato com responsável/serviço/status custom. cup_task_id
    default = task_id; passe '' para simular cliente sem vínculo."""
    link = task_id if cup_task_id is None else (cup_task_id or None)
    with TS() as s:
        c = Cliente(
            slug=nome.lower().replace(" ", "-"), nome=nome,
            categoria=Categoria.ECOMMERCE, gestor=gestor,
            cup_task_id=link, ativo=True,
        )
        s.add(c)
        s.execute(
            text("INSERT INTO staging.cup_contratos "
                 "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                 "VALUES (:sub, :task, 'Gestão de Performance', :st, :resp, :dt)"),
            {"sub": task_id + "-s", "task": task_id, "st": status,
             "resp": resp, "dt": data_inicio},
        )
        s.commit()
        s.refresh(c)
        return c.id


def test_sync_normaliza_capitalizacao_do_responsavel(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_resp(TS, nome="Loja N", gestor="Rayan Coutinho",
                             task_id="tn", resp="rayan coutinho")
    client = TestClient(app)
    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Rayan Coutinho"


def test_sync_ignora_cliente_sem_vinculo(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_resp(TS, nome="Loja SV", gestor="Velho",
                             task_id="tsv", resp="Novo Gestor", cup_task_id="")
    client = TestClient(app)
    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    assert r.json()["atualizados"] == 0
    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Velho"


def test_sync_prefere_contrato_ativo(app_with_db):
    app, TS = app_with_db
    with TS() as s:
        c = Cliente(slug="loja-ac", nome="Loja AC", categoria=Categoria.ECOMMERCE,
                    gestor="Velho", cup_task_id="tac", ativo=True)
        s.add(c)
        for sub, st, resp, dt in [
            ("tac-1", "cancelado/inativo", "Antigo", date(2026, 5, 1)),
            ("tac-2", "ativo", "Atual", date(2026, 1, 1)),
        ]:
            s.execute(
                text("INSERT INTO staging.cup_contratos "
                     "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                     "VALUES (:sub, 'tac', 'Gestão de Performance', :st, :resp, :dt)"),
                {"sub": sub, "st": st, "resp": resp, "dt": dt},
            )
        s.commit(); s.refresh(c); cid = c.id
    client = TestClient(app)
    r = client.post("/gestor/clientes/sync-gestores")
    assert r.status_code == 200, r.text
    with TS() as s:
        assert s.get(Cliente, cid).gestor == "Atual"
```

- [ ] **Step 3: Rodar os novos testes e verificar que falham**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_sync_gestores.py -q`
Expected: FAIL — o sync atual casa por nome (não por `id_task`) e não normaliza, então `test_sync_normaliza_capitalizacao_do_responsavel` e `test_sync_prefere_contrato_ativo` falham.

- [ ] **Step 4: Reescrever `sync_gestores_from_clickup`**

Em `web/backend/api/gestor.py`, substitua TODO o corpo da função `sync_gestores_from_clickup` (linhas ~390-543, da docstring até o `return`) por:

```python
    """Atribui clientes.gestor = responsável do contrato 'Performance' vigente
    no ClickUp, seguindo o vínculo cup_task_id.

    Caminho do dado (relaciona por cup_task_id, NÃO por nome):
      clientes.cup_task_id  →  staging.cup_contratos.id_task
                               ↓ filtra servico ILIKE '%performance%'
                               ↓ contrato vigente mais recente (services.clickup_match)
                               responsavel → normalize_gestor_name → clientes.gestor
    """
    from services.clickup_match import responsavel_performance

    rows = session.execute(
        text("""
            SELECT c.id::text AS cliente_id, c.gestor, c.gestor_travado,
                   ct.servico, ct.status, ct.responsavel, ct.data_inicio
            FROM clientes c
            JOIN staging.cup_contratos ct ON ct.id_task = c.cup_task_id
            WHERE c.ativo = true AND c.cup_task_id IS NOT NULL
        """)
    ).mappings().all()

    # Agrupa contratos por cliente
    por_cliente: dict[str, dict] = {}
    for r in rows:
        ent = por_cliente.setdefault(r["cliente_id"], {
            "gestor_atual": r["gestor"],
            "gestor_travado": r["gestor_travado"],
            "contratos": [],
        })
        ent["contratos"].append({
            "servico": r["servico"], "status": r["status"],
            "responsavel": r["responsavel"], "data_inicio": r["data_inicio"],
        })

    com_vinculo = session.execute(
        text("SELECT COUNT(*) FROM clientes WHERE ativo = true AND cup_task_id IS NOT NULL")
    ).scalar() or 0
    total_ativos = session.execute(
        text("SELECT COUNT(*) FROM clientes WHERE ativo = true")
    ).scalar() or 0

    com_contrato_performance = 0
    com_responsavel = 0
    a_atualizar = 0
    atualizados = 0

    for cliente_id, ent in por_cliente.items():
        resp_bruto = responsavel_performance(ent["contratos"])
        if resp_bruto is None:
            continue
        com_contrato_performance += 1
        com_responsavel += 1
        novo = normalize_gestor_name(resp_bruto)
        if ent["gestor_travado"]:
            continue
        if ent["gestor_atual"] == novo:
            continue
        a_atualizar += 1
        res = session.execute(
            update(Cliente)
            .where(Cliente.id == uuid.UUID(cliente_id),
                   Cliente.gestor_travado == False)  # noqa: E712
            .values(gestor=novo, atualizado_em=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        atualizados += res.rowcount

    session.commit()

    _log.info(
        "sync-gestores: atualizados=%d a_atualizar=%d total_ativos=%d com_vinculo=%d "
        "com_contrato_performance=%d com_responsavel=%d",
        atualizados, a_atualizar, total_ativos, com_vinculo,
        com_contrato_performance, com_responsavel,
    )

    return {
        "atualizados": atualizados,
        "a_atualizar": a_atualizar,
        "total_ativos": total_ativos,
        "com_vinculo": com_vinculo,
        "com_match_nome": com_vinculo,  # alias retrocompatível (deprecado)
        "com_contrato_performance": com_contrato_performance,
        "com_responsavel": com_responsavel,
    }
```

- [ ] **Step 5: Rodar a suíte de sync e verificar que passa**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_sync_gestores.py -q`
Expected: PASS (incluindo os testes pré-existentes `test_sync_sobrescreve_gestor_alterado`, `test_sync_respeita_gestor_travado`, `test_sync_idempotente` e os novos).

- [ ] **Step 6: Commit**

```bash
cd /Users/mac0267/Documents/auto-report-main
git add web/backend/api/gestor.py web/backend/tests/test_sync_gestores.py
git commit -m "feat(gestores): sync-gestores via cup_task_id + contrato vigente + normalize"
```

---

## Task 3: `automatch` por proximidade

**Files:**
- Modify: `web/backend/api/gestor.py:298-381` (`automatch_clickup`)
- Test: `web/backend/tests/test_sync_gestores.py`

- [ ] **Step 1: Escrever testes de automatch por proximidade**

Em `web/backend/tests/test_sync_gestores.py`, adicione:

```python
def _seed_cup_cliente(TS, task_id, nome):
    with TS() as s:
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome) VALUES (:t, :n)"),
            {"t": task_id, "n": nome},
        )
        s.commit()

def _seed_cliente_sem_cup(TS, nome):
    with TS() as s:
        c = Cliente(slug=nome.lower().replace(" ", "-"), nome=nome,
                    categoria=Categoria.ECOMMERCE, ativo=True, cup_task_id=None)
        s.add(c); s.commit(); s.refresh(c)
        return str(c.id)


def test_automatch_auto_aplica_match_forte(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_sem_cup(TS, "Noway Drinks")
    _seed_cup_cliente(TS, "cup-noway", "Noway Drink")
    _seed_cup_cliente(TS, "cup-outro", "Padaria do Zé")
    client = TestClient(app)

    prev = client.post("/gestor/clickup/automatch?dry_run=true")
    assert prev.status_code == 200, prev.text
    body = prev.json()
    assert any(m["cliente_nome"] == "Noway Drinks" and m["task_id"] == "cup-noway"
               for m in body["matches"])
    assert body["matches"][0]["score"] >= 0.90

    apply = client.post("/gestor/clickup/automatch?dry_run=false")
    assert apply.status_code == 200, apply.text
    assert apply.json()["aplicados"] >= 1
    with TS() as s:
        assert s.get(Cliente, __import__("uuid").UUID(cid)).cup_task_id == "cup-noway"


def test_automatch_nao_aplica_lixo(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_sem_cup(TS, "Nomã")
    _seed_cup_cliente(TS, "cup-bueno", "Bueno Mate")
    client = TestClient(app)
    body = client.post("/gestor/clickup/automatch?dry_run=false").json()
    assert all(m["cliente_nome"] != "Nomã" for m in body["matches"])
    with TS() as s:
        assert s.get(Cliente, __import__("uuid").UUID(cid)).cup_task_id is None
```

- [ ] **Step 2: Rodar e verificar que falham**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_sync_gestores.py -k automatch -q`
Expected: FAIL — o automatch atual só casa por nome exato normalizado, então não há `score` na resposta e "Noway Drinks" não casa com "Noway Drink".

- [ ] **Step 3: Reescrever `automatch_clickup`**

Em `web/backend/api/gestor.py`, substitua o corpo de `automatch_clickup` (linhas ~303-381, do primeiro `cup_rows = ...` até o `return`) por:

```python
    from services.clickup_match import melhores_candidatos, classificar

    cup_rows = [
        {"task_id": r["task_id"], "nome": r["nome"]}
        for r in session.execute(
            text("SELECT task_id, nome FROM staging.cup_clientes "
                 "WHERE nome IS NOT NULL AND TRIM(nome) <> ''")
        ).mappings().all()
    ]

    clientes = session.execute(
        select(Cliente)
        .where(Cliente.cup_task_id.is_(None), Cliente.ativo == True)  # noqa: E712
        .order_by(Cliente.nome.asc())
    ).scalars().all()

    matches: list[dict] = []
    ambiguos: list[dict] = []
    sem_candidato: list[dict] = []

    for c in clientes:
        cands = melhores_candidatos(c.nome, cup_rows, k=5)
        cls = classificar(cands)
        if cls == "auto":
            sc, tid, cup_nome = cands[0]
            matches.append({
                "cliente_id": str(c.id), "cliente_nome": c.nome,
                "task_id": tid, "cup_nome": cup_nome, "score": round(sc, 3),
            })
        elif cls == "sugestao":
            ambiguos.append({
                "cliente_id": str(c.id), "cliente_nome": c.nome,
                "candidatos": [
                    {"task_id": tid, "nome": nome, "score": round(sc, 3)}
                    for sc, tid, nome in cands if sc >= 0.70
                ],
            })
        else:
            sem_candidato.append({"cliente_id": str(c.id), "cliente_nome": c.nome})

    aplicados = 0
    if not dry_run and matches:
        for m in matches:
            ja_usado = session.execute(
                select(Cliente.id).where(Cliente.cup_task_id == m["task_id"])
            ).scalar_one_or_none()
            if ja_usado is not None:
                continue
            session.execute(
                update(Cliente)
                .where(Cliente.id == uuid.UUID(m["cliente_id"]))
                .values(cup_task_id=m["task_id"])
            )
            aplicados += 1
        session.commit()
        _log.info("automatch: aplicados=%d (de %d propostos)", aplicados, len(matches))

    return {
        "dry_run": dry_run,
        "matches": matches,
        "aplicados": aplicados,
        "ambiguos": ambiguos,
        "sem_candidato": sem_candidato,
        "stats": {
            "total_clientes_sem_vinculo": len(clientes),
            "matches_propostos": len(matches),
            "ambiguos": len(ambiguos),
            "sem_candidato": len(sem_candidato),
        },
    }
```

- [ ] **Step 4: Rodar e verificar que passam**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_sync_gestores.py -k automatch -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/mac0267/Documents/auto-report-main
git add web/backend/api/gestor.py web/backend/tests/test_sync_gestores.py
git commit -m "feat(gestores): automatch por proximidade com guardas anti-falso-positivo"
```

---

## Task 4: Endpoint `sync-tudo` (encadeamento)

**Files:**
- Modify: `web/backend/api/gestor.py` (adicionar endpoint após `sync_gestores_from_clickup`)
- Test: `web/backend/tests/test_sync_gestores.py`

- [ ] **Step 1: Escrever o teste de encadeamento**

Em `web/backend/tests/test_sync_gestores.py`, adicione:

```python
def test_sync_tudo_vincula_e_preenche_gestor(app_with_db):
    app, TS = app_with_db
    cid = _seed_cliente_sem_cup(TS, "Zacca")
    _seed_cup_cliente(TS, "cup-zacca", "Zacca Brasil")
    with TS() as s:
        s.execute(
            text("INSERT INTO staging.cup_contratos "
                 "(id_subtask, id_task, servico, status, responsavel, data_inicio) "
                 "VALUES ('z-1', 'cup-zacca', 'Gestão de Performance', 'ativo', "
                 "'thiago m.', :dt)"),
            {"dt": date(2026, 1, 1)},
        )
        s.commit()
    client = TestClient(app)

    r = client.post("/gestor/clickup/sync-tudo")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vinculos_aplicados"] >= 1
    assert body["gestores_atualizados"] >= 1
    with TS() as s:
        c = s.get(Cliente, __import__("uuid").UUID(cid))
        assert c.cup_task_id == "cup-zacca"
        assert c.gestor == "Thiago M."
```

- [ ] **Step 2: Rodar e verificar que falha**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_sync_gestores.py -k sync_tudo -q`
Expected: FAIL com 404 (rota não existe).

- [ ] **Step 3: Implementar o endpoint**

Em `web/backend/api/gestor.py`, logo após a função `sync_gestores_from_clickup` (antes de `# ── GET /gestor/clientes ──`), adicione:

```python
# ── POST /gestor/clickup/sync-tudo ─────────────────────────────────────────
# Encadeia: automatch (aplica só vínculos de alta confiança) → sync-gestores.
# Não auto-aplica nada de baixa confiança; sugestões ficam para revisão manual.

@router.post("/clickup/sync-tudo", status_code=200)
def sync_tudo(
    user: Usuario = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    automatch = automatch_clickup(dry_run=False, user=user, session=session)
    gestores = sync_gestores_from_clickup(user=user, session=session)
    return {
        "vinculos_aplicados": automatch["aplicados"],
        "sugestoes_pendentes": automatch["stats"]["ambiguos"],
        "sem_candidato": automatch["stats"]["sem_candidato"],
        "gestores_atualizados": gestores["atualizados"],
        "automatch": automatch,
        "gestores": gestores,
    }
```

- [ ] **Step 4: Rodar e verificar que passa**

Run: `cd web/backend && .venv/bin/python -m pytest tests/test_sync_gestores.py -k sync_tudo -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/mac0267/Documents/auto-report-main
git add web/backend/api/gestor.py web/backend/tests/test_sync_gestores.py
git commit -m "feat(gestores): endpoint sync-tudo encadeia vínculo automático e gestor"
```

---

## Task 5: Verificação final

**Files:** nenhum (verificação)

- [ ] **Step 1: Rodar a suíte completa do backend**

Run: `cd web/backend && .venv/bin/python -m pytest -q`
Expected: todos os testes PASS (sem regressão nas demais suítes).

- [ ] **Step 2: (Opcional, read-only) Dry-run contra produção**

Apenas leitura — NÃO aplica nada. Confirma quantos clientes seriam auto-vinculados pela proximidade nova, comparando com a expectativa do spec (~14–16 de 24). Requer o `.env` de produção configurado.

Run:
```bash
cd web/backend && .venv/bin/python - <<'PY'
import psycopg
from services.clickup_match import melhores_candidatos, classificar
URL = "postgresql://postgres:Turbosenha*@34.95.249.110:5432/autoreport"
with psycopg.connect(URL) as conn:
    semv = conn.execute("SELECT nome FROM clientes WHERE ativo AND cup_task_id IS NULL").fetchall()
    cup = [{"task_id": t, "nome": n} for t, n in
           conn.execute("SELECT task_id, nome FROM staging.cup_clientes WHERE nome IS NOT NULL AND TRIM(nome)<>''").fetchall()]
auto = sug = sem = 0
for (nome,) in semv:
    cls = classificar(melhores_candidatos(nome, cup))
    auto += cls == "auto"; sug += cls == "sugestao"; sem += cls == "sem_candidato"
print(f"auto={auto} sugestao={sug} sem_candidato={sem} (de {len(semv)})")
PY
```
Expected: `auto` entre ~12 e ~18; nenhum vínculo claramente errado entre os `auto` (inspecionar a lista se necessário). A aplicação real em produção (`POST /gestor/clickup/sync-tudo`) é uma ação de operação executada manualmente pelo admin, fora deste plano.

- [ ] **Step 3: Abrir PR**

```bash
cd /Users/mac0267/Documents/auto-report-main
git push -u origin fix/sync-gestores-cup-task-id
gh pr create --title "fix(gestores): sincronização correta de gestores via ClickUp" \
  --body "$(cat <<'EOF'
## Problema
Gestor de 24/75 clientes ficava preso no valor antigo da planilha: o sync casava por nome exato e ignorava o vínculo `cup_task_id`.

## Solução
- `sync-gestores` segue `cup_task_id` → contrato Performance vigente → responsável normalizado.
- `automatch` passa a usar proximidade de nome com guardas anti-falso-positivo (auto-aplica só score ≥ 0.90 sem ambiguidade).
- Novo `POST /clickup/sync-tudo` encadeia vínculo → gestor.
- Lógica pura isolada em `services/clickup_match.py`, com golden set dos 24 casos reais.

Spec: `docs/superpowers/specs/2026-06-01-sync-gestores-clickup-design.md`
Plano: `docs/superpowers/plans/2026-06-01-sync-gestores-clickup.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notas de risco (do spec)

- **rapidfuzz no deploy Render:** validado no Step 2 da Task 1 (instala via pip). Fallback `difflib` se necessário.
- **Frontend `ln`/`ln_id`:** `api-gestor.ts` chama `clickup/ln`, `clientes/ln`, `clientes/{id}/ln`, que não batem com as rotas reais (`clickup/automatch`, `clientes/sync-gestores`, `clientes/{id}/cup-task`). Fora do escopo deste plano (backend), mas investigar antes de validar a tela ponta-a-ponta — pode ser alias faltante.
- **Clientes inexistentes no ClickUp** (`Sim! Cerveja`, talvez `Cosmobeauty`): permanecem sem vínculo; resolução manual via `/clickup/tasks`. Esperado.

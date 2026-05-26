"""Teste do endpoint /cliente/metricas/highlight.

Reaproveita a fixture `app_with_db` de test_cliente_metricas.py via import.
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import text

from models import Cliente
from models.cliente import Categoria
from models.snapshot import Frequencia, Snapshot

from tests.test_cliente_metricas import app_with_db  # noqa: F401  (fixture)

# Senha global da área do cliente (padrão do Settings)
_GLOBAL_PASSWORD = "Warley20192020"


def _seed_with_snaps(TS, *, nome, cnpj, task_id, snaps):
    """snaps: lista de (mes_yyyymm, faturamento, roas, fat_var_pct)."""
    with TS() as s:
        c = Cliente(
            slug=nome.lower(),
            nome=nome,
            categoria=Categoria.LEAD_COM_SITE,
            cup_task_id=task_id,
            ativo=True,
        )
        s.add(c); s.commit(); s.refresh(c)
        s.execute(
            text("INSERT INTO staging.cup_clientes (task_id, nome, cnpj) VALUES (:t, :n, :c)"),
            {"t": task_id, "n": nome, "c": cnpj},
        )
        for mes, fat, roas, fat_var in snaps:
            ano, m = int(mes[:4]), int(mes[5:7])
            s.add(Snapshot(
                cliente_id=c.id,
                periodo_inicio=date(ano, m, 1),
                periodo_fim=date(ano, m, 28),
                frequencia=Frequencia.MENSAL,
                faturamento=Decimal(str(fat)),
                investimento=Decimal("100"),
                roas=Decimal(str(roas)),
                faturamento_var_pct=Decimal(str(fat_var)) if fat_var is not None else None,
            ))
        s.commit()
        return c.id


def _login(client: TestClient, cnpj: str) -> str:
    """Faz login com a senha global e devolve o token Bearer."""
    r = client.post("/cliente/auth/login", json={"cnpj": cnpj, "senha": _GLOBAL_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.text}"
    return r.json()["token"]


def test_highlight_returns_401_without_token(app_with_db):
    app, _ = app_with_db
    client = TestClient(app)
    r = client.get("/cliente/metricas/highlight")
    assert r.status_code == 401


def test_highlight_returns_null_with_few_data(app_with_db):
    app, TS = app_with_db
    snaps = [("2026-04", 1000, 3.5, None), ("2026-05", 1100, 3.6, None)]
    _seed_with_snaps(TS, nome="loja-a", cnpj="11111111000111", task_id="t-a", snaps=snaps)

    client = TestClient(app)
    tok = _login(client, "11111111000111")
    r = client.get("/cliente/metricas/highlight", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json() == {"highlight": None}


def test_highlight_returns_best_roas_window(app_with_db):
    app, TS = app_with_db
    snaps = [(f"2025-{m:02d}", 1000, 2.5, None) for m in range(6, 13)] + \
            [(f"2026-{m:02d}", 1100, 2.6, None) for m in range(1, 5)] + \
            [("2026-05", 1200, 4.2, None)]
    _seed_with_snaps(TS, nome="loja-b", cnpj="22222222000122", task_id="t-b", snaps=snaps)

    client = TestClient(app)
    tok = _login(client, "22222222000122")
    r = client.get("/cliente/metricas/highlight", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["highlight"] is not None
    assert body["highlight"]["type"] == "best_roas_window"
    assert body["highlight"]["value"] == 4.2

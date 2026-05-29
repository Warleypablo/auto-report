"""Auditoria de IDs de conta de anúncio.

Lista clientes ATIVOS que estão sem `id_meta_ads` e/ou `id_google_ads`.
Saída: tabela no stdout + arquivo CSV (default: audit_ids.csv).

Uso (a partir de web/backend/):
    .venv/bin/python -m scripts.audit_ids [--csv CAMINHO]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import TextIO

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db import SessionLocal  # noqa: E402
from models import Cliente  # noqa: E402

_COLS = ["slug", "nome", "falta_meta", "falta_google"]


def auditar_ids(session: Session) -> list[dict]:
    """Retorna clientes ativos sem id_meta_ads e/ou id_google_ads, ordenados por slug."""
    stmt = (
        select(Cliente)
        .where(Cliente.ativo.is_(True))
        .where((Cliente.id_meta_ads.is_(None)) | (Cliente.id_google_ads.is_(None)))
        .order_by(Cliente.slug)
    )
    rows: list[dict] = []
    for c in session.scalars(stmt):
        rows.append(
            {
                "slug": c.slug,
                "nome": c.nome,
                "falta_meta": c.id_meta_ads is None,
                "falta_google": c.id_google_ads is None,
            }
        )
    return rows


def formatar_tabela(rows: list[dict]) -> str:
    """Formata os resultados como tabela alinhada para o stdout."""
    largs = {col: len(col) for col in _COLS}
    for r in rows:
        for col in _COLS:
            largs[col] = max(largs[col], len(str(r[col])))
    linhas = ["  ".join(col.ljust(largs[col]) for col in _COLS)]
    linhas.append("  ".join("-" * largs[col] for col in _COLS))
    for r in rows:
        linhas.append("  ".join(str(r[col]).ljust(largs[col]) for col in _COLS))
    linhas.append("")
    linhas.append(f"Total: {len(rows)} cliente(s) ativo(s) com ID faltante.")
    return "\n".join(linhas)


def escrever_csv(rows: list[dict], fp: TextIO) -> None:
    """Escreve os resultados como CSV (cabeçalho _COLS) no file-like `fp`."""
    writer = csv.writer(fp)
    writer.writerow(_COLS)
    for r in rows:
        writer.writerow([str(r[col]) for col in _COLS])


def main() -> list[dict]:
    parser = argparse.ArgumentParser(description="Auditoria de IDs de conta de anúncio.")
    parser.add_argument("--csv", default="audit_ids.csv", help="Caminho do CSV de saída.")
    args = parser.parse_args()

    with SessionLocal() as session:
        rows = auditar_ids(session)

    print(formatar_tabela(rows))
    with open(args.csv, "w", newline="", encoding="utf-8") as fp:
        escrever_csv(rows, fp)
    print(f"CSV gravado em: {args.csv}")
    return rows


if __name__ == "__main__":
    main()

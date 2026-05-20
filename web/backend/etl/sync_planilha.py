"""Sync rápido: importa todos os clientes da Planilha Central para o DB.

Só metadata (nome, categoria, setor, etc.). NÃO chama gathers (Meta/Google/GA4),
então não cria snapshots — só sincroniza a estrutura. Faz leitura tolerante a
linhas incompletas / colunas ausentes (mais robusta que core.fetch_clientes).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Garante que core/ (raiz do auto-report) está no PYTHONPATH
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select

from db import SessionLocal
from models import Categoria, Cliente
from .cliente_publico import ClientePublico, slugify

log = logging.getLogger(__name__)


# Constantes de coluna duplicadas do core (intencionalmente — não acoplamos ao parser do core,
# que falha em linhas curtas). Devem casar com COL_* em core/leitura_central.py.
COL_CLIENTE = "CLIENTE"
COL_CATEGORIA = "CATEGORIA"
COL_PUBLICAR = "PUBLICAR_VITRINE"
COL_DESCRICAO = "DESCRICAO_PUBLICA"
COL_LOGO = "LOGO_URL"
COL_SETOR_PUB = "SETOR_PUBLICO"
COL_PORTE_PUB = "PORTE_PUBLICO"

_TRUE = {"TRUE", "VERDADEIRO", "SIM", "X", "1", "Y", "YES"}


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _is_true(v: str) -> bool:
    return v.upper() in _TRUE


def sync_clientes() -> dict:
    """Lê a Planilha Central e faz upsert de todos os clientes no DB.

    Retorna {inserted, updated, skipped, total, problemas}.
    """
    from config.settings import CENTRAL_SHEET_URL, CENTRAL_TAB_NAME
    from core.leitura_central import _fetch_values, parse_sheet_id

    log.info("sync_clientes_iniciado")
    spreadsheet_id = parse_sheet_id(CENTRAL_SHEET_URL)
    rows = _fetch_values(spreadsheet_id, CENTRAL_TAB_NAME)
    if not rows:
        return {"inserted": 0, "updated": 0, "skipped": 0, "total": 0, "problemas": ["planilha vazia"]}

    header = {c.strip().upper(): i for i, c in enumerate(rows[0])}
    col_cliente = header.get(COL_CLIENTE)
    col_categoria = header.get(COL_CATEGORIA)

    if col_cliente is None or col_categoria is None:
        raise ValueError(f"Colunas obrigatórias ausentes. Esperadas: {COL_CLIENTE}, {COL_CATEGORIA}. Header: {list(header)}")

    inserted = 0
    updated = 0
    skipped = 0
    problemas: list[str] = []

    # Etapa 1: parse + dedupe (slug colide quando dois nomes diferentes viram o mesmo slug)
    desejados: dict[str, dict] = {}
    for row_idx, row in enumerate(rows[1:], start=2):
        nome = _cell(row, col_cliente)
        if not nome:
            continue

        categoria_str = _cell(row, col_categoria)
        if not categoria_str:
            problemas.append(f"linha {row_idx} ({nome}): sem categoria")
            skipped += 1
            continue

        try:
            categoria_enum = Categoria(categoria_str)
        except ValueError:
            problemas.append(f"linha {row_idx} ({nome}): categoria desconhecida '{categoria_str}'")
            skipped += 1
            continue

        slug = slugify(nome)
        payload = dict(
            slug=slug,
            nome=nome,
            categoria=categoria_enum,
            publicar_vitrine=_is_true(_cell(row, header.get(COL_PUBLICAR))),
            descricao_publica=_cell(row, header.get(COL_DESCRICAO)) or None,
            logo_url=_cell(row, header.get(COL_LOGO)) or None,
            setor=_cell(row, header.get(COL_SETOR_PUB)) or None,
            porte=_cell(row, header.get(COL_PORTE_PUB)) or None,
            row_idx=row_idx,
        )

        prev = desejados.get(slug)
        if prev:
            problemas.append(
                f"slug duplicado '{slug}' — linhas {prev['row_idx']} ({prev['nome']}) e {row_idx} ({nome}); mantendo a primeira"
            )
            continue
        desejados[slug] = payload

    # Etapa 2: aplicar no DB (fetch único, insert/update por slug)
    with SessionLocal() as session:
        existentes = {
            c.slug: c
            for c in session.scalars(select(Cliente).where(Cliente.slug.in_(desejados.keys()))).all()
        }
        for slug, p in desejados.items():
            existing = existentes.get(slug)
            if existing:
                existing.nome = p["nome"]
                existing.categoria = p["categoria"]
                if p["logo_url"]:
                    existing.logo_url = p["logo_url"]
                if p["descricao_publica"]:
                    existing.descricao_publica = p["descricao_publica"]
                if p["setor"]:
                    existing.setor = p["setor"]
                if p["porte"]:
                    existing.porte = p["porte"]
                existing.publicar_vitrine = p["publicar_vitrine"]
                updated += 1
            else:
                session.add(Cliente(
                    slug=slug,
                    nome=p["nome"],
                    categoria=p["categoria"],
                    logo_url=p["logo_url"],
                    descricao_publica=p["descricao_publica"],
                    setor=p["setor"],
                    porte=p["porte"],
                    publicar_vitrine=p["publicar_vitrine"],
                    destaque=False,
                ))
                inserted += 1

        session.commit()

    resumo = {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total": inserted + updated,
        "problemas": problemas[:20],  # cap p/ não inflar response
    }
    log.info("sync_clientes_finalizado", extra={k: v for k, v in resumo.items() if k != "problemas"})
    return resumo

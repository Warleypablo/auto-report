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
COL_GESTOR = "GESTOR"
COL_PUBLICAR = "PUBLICAR_VITRINE"
COL_DESCRICAO = "DESCRICAO_PUBLICA"
COL_LOGO = "LOGO_URL"
COL_SETOR_PUB = "SETOR_PUBLICO"
COL_PORTE_PUB = "PORTE_PUBLICO"
COL_PAINEL    = "LINK PAINEL DE CONTROLE"
COL_PASTA     = "LINK PASTA"
COL_IDGOOGLE  = "ID GOOGLE ADS"
COL_IDMETA    = "ID META ADS"
COL_IDGA4     = "ID GA4"

_TRUE = {"TRUE", "VERDADEIRO", "SIM", "X", "1", "Y", "YES"}


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _is_true(v: str) -> bool:
    return v.upper() in _TRUE


def fetch_clientes_tolerante() -> list:
    """Lê todos os clientes da Planilha Central como core.Cliente, tolerante a linhas curtas.

    Substituto local para core.leitura_central.fetch_clientes(atualizar=False), que
    falha quando uma linha tem menos colunas que o header.
    """
    from config.settings import CENTRAL_SHEET_URL, CENTRAL_TAB_NAME
    from core.leitura_central import (
        _fetch_values,
        parse_sheet_id,
        Cliente as CoreCliente,
        COL_CATEGORIA,
        COL_CLIENTE,
        COL_PAINEL,
        COL_PASTA,
        COL_IDGOOGLE,
        COL_IDMETA,
        COL_IDGA4,
        COL_STATUS,
        COL_LASTGEN,
    )

    spreadsheet_id = parse_sheet_id(CENTRAL_SHEET_URL)
    rows = _fetch_values(spreadsheet_id, CENTRAL_TAB_NAME)
    if not rows:
        return []

    header = {c.strip().upper(): i for i, c in enumerate(rows[0])}
    status_idx = header.get(COL_STATUS)
    lastgen_idx = header.get(COL_LASTGEN)

    out = []
    for row_idx, row in enumerate(rows[1:], start=2):
        nome = _cell(row, header.get(COL_CLIENTE))
        if not nome:
            continue
        categoria = _cell(row, header.get(COL_CATEGORIA))
        if not categoria:
            continue
        extras = {
            "_sheet_id": spreadsheet_id,
            "_tab": CENTRAL_TAB_NAME,
            "_row": row_idx,
            "_status_idx": status_idx,
            "_lastgen_idx": lastgen_idx,
        }
        # Inclui todas as colunas extras que não são "core" (para ClientePublico ler)
        for k, idx in header.items():
            if k in {COL_CATEGORIA, COL_CLIENTE, COL_PAINEL, COL_PASTA,
                     COL_IDGOOGLE, COL_IDMETA, COL_IDGA4, COL_STATUS, COL_LASTGEN}:
                continue
            extras[k] = _cell(row, idx)

        out.append(
            CoreCliente(
                nome=nome,
                categoria=categoria,
                painel_url=_cell(row, header.get(COL_PAINEL)),
                pasta_url=_cell(row, header.get(COL_PASTA)),
                id_google_ads=_cell(row, header.get(COL_IDGOOGLE)),
                id_meta_ads=_cell(row, header.get(COL_IDMETA)),
                id_ga4=_cell(row, header.get(COL_IDGA4)),
                extras=extras,
            )
        )
    return out


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
            gestor=_cell(row, header.get(COL_GESTOR)) or None,
            id_google_ads=_cell(row, header.get(COL_IDGOOGLE)) or None,
            id_meta_ads=_cell(row, header.get(COL_IDMETA)) or None,
            id_ga4=_cell(row, header.get(COL_IDGA4)) or None,
            painel_url=_cell(row, header.get(COL_PAINEL)) or None,
            pasta_url=_cell(row, header.get(COL_PASTA)) or None,
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
                # Campos estruturais: sempre sincroniza da planilha
                existing.nome = p["nome"]
                existing.categoria = p["categoria"]
                existing.publicar_vitrine = p["publicar_vitrine"]
                # Campos opcionais estruturais: só atualiza se vieram preenchidos
                if p["logo_url"]:
                    existing.logo_url = p["logo_url"]
                if p["descricao_publica"]:
                    existing.descricao_publica = p["descricao_publica"]
                if p["setor"]:
                    existing.setor = p["setor"]
                if p["porte"]:
                    existing.porte = p["porte"]
                # Campos operacionais editáveis: só preenche se ainda NULL no DB
                # (primeira carga), preservando edições manuais posteriores
                if existing.gestor is None and p["gestor"]:
                    existing.gestor = p["gestor"]
                if existing.id_google_ads is None and p["id_google_ads"]:
                    existing.id_google_ads = p["id_google_ads"]
                if existing.id_meta_ads is None and p["id_meta_ads"]:
                    existing.id_meta_ads = p["id_meta_ads"]
                if existing.id_ga4 is None and p["id_ga4"]:
                    existing.id_ga4 = p["id_ga4"]
                if existing.painel_url is None and p["painel_url"]:
                    existing.painel_url = p["painel_url"]
                if existing.pasta_url is None and p["pasta_url"]:
                    existing.pasta_url = p["pasta_url"]
                updated += 1
            else:
                session.add(Cliente(
                    slug=slug,
                    nome=p["nome"],
                    categoria=p["categoria"],
                    gestor=p["gestor"],
                    id_google_ads=p["id_google_ads"],
                    id_meta_ads=p["id_meta_ads"],
                    id_ga4=p["id_ga4"],
                    painel_url=p["painel_url"],
                    pasta_url=p["pasta_url"],
                    logo_url=p["logo_url"],
                    descricao_publica=p["descricao_publica"],
                    setor=p["setor"],
                    porte=p["porte"],
                    publicar_vitrine=p["publicar_vitrine"],
                    destaque=False,
                    ativo=True,
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

"""Sync rápido: importa todos os clientes da Planilha Central para o DB.

Só metadata (nome, categoria, setor, etc.). NÃO chama gathers (Meta/Google/GA4),
então não cria snapshots — só sincroniza a estrutura. Clientes que ainda não
existiam aparecem com publicar_vitrine=False (opt-in deliberado).

Para popular snapshots, use o ETL completo (etl.collect.run_etl).
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


def sync_clientes() -> dict:
    """Lê a Planilha Central e faz upsert de todos os clientes no DB.

    Retorna {inserted, updated, skipped, total}.
    """
    from config.settings import CENTRAL_SHEET_URL, CENTRAL_TAB_NAME
    from core.leitura_central import fetch_clientes

    log.info("sync_clientes_iniciado")
    todos = fetch_clientes(
        atualizar=False,
        sheet_url=CENTRAL_SHEET_URL,
        tab_name=CENTRAL_TAB_NAME,
    )

    inserted = 0
    updated = 0
    skipped = 0

    with SessionLocal() as session:
        for c in todos:
            # Cliente do core não tem slug — derivamos do nome
            if not c.nome or not c.categoria:
                skipped += 1
                continue

            try:
                categoria_enum = Categoria(c.categoria)
            except ValueError:
                log.warning(
                    "sync_categoria_desconhecida",
                    extra={"cliente": c.nome, "categoria": c.categoria},
                )
                skipped += 1
                continue

            slug = slugify(c.nome)
            pub = ClientePublico.from_cliente(c)

            existing = session.scalar(select(Cliente).where(Cliente.slug == slug))
            if existing:
                existing.nome = c.nome
                existing.categoria = categoria_enum
                # só sobrescreve metadados públicos se vieram preenchidos na planilha
                if pub.logo_url:
                    existing.logo_url = pub.logo_url
                if pub.descricao_publica:
                    existing.descricao_publica = pub.descricao_publica
                if pub.setor:
                    existing.setor = pub.setor
                if pub.porte:
                    existing.porte = pub.porte
                # publicar_vitrine vem direto da planilha (opt-in autoritativo)
                existing.publicar_vitrine = pub.publicar_vitrine
                updated += 1
            else:
                novo = Cliente(
                    slug=slug,
                    nome=c.nome,
                    categoria=categoria_enum,
                    logo_url=pub.logo_url,
                    descricao_publica=pub.descricao_publica,
                    setor=pub.setor,
                    porte=pub.porte,
                    publicar_vitrine=pub.publicar_vitrine,
                    destaque=False,
                )
                session.add(novo)
                inserted += 1

        session.commit()

    resumo = {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total": inserted + updated,
    }
    log.info("sync_clientes_finalizado", extra=resumo)
    return resumo

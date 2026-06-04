"""Cria usuarios + usuario_clientes para todos os gestores com clientes ativos.

Idempotente: re-rodar não duplica registros.

Usage (from project root):
    python web/backend/scripts/seed_gestores_acesso.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from api.auth import hash_password
from db import SessionLocal
from models import Cliente, GestorCadastrado, Usuario, UsuarioCliente

_CONECTIVAS = {"da", "de", "do", "das", "dos", "e", "von", "van", "del"}
_SENHA_PADRAO = "turbo@2026"
_DOMINIO = "turbopartners.com.br"


def _remover_acentos(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def _derivar_email(nome: str) -> str:
    tokens = [t for t in nome.split() if t.lower() not in _CONECTIVAS]
    if not tokens:
        raise ValueError(f"Nome sem tokens válidos: {nome!r}")
    primeiro = _remover_acentos(tokens[0]).lower()
    ultimo = _remover_acentos(tokens[-1]).lower() if len(tokens) > 1 else primeiro
    return f"{primeiro}.{ultimo}@{_DOMINIO}"


def main(dry_run: bool = False) -> None:
    with SessionLocal() as session:
        gestores = session.execute(
            select(GestorCadastrado).order_by(GestorCadastrado.nome)
        ).scalars().all()

        criados = 0
        vinculos = 0

        for g in gestores:
            clientes_ativos = session.execute(
                select(Cliente).where(Cliente.gestor == g.nome, Cliente.ativo.is_(True))
            ).scalars().all()

            if not clientes_ativos:
                print(f"  SKIP {g.nome!r} — sem clientes ativos")
                continue

            email = _derivar_email(g.nome)

            usuario = session.execute(
                select(Usuario).where(Usuario.email == email)
            ).scalar_one_or_none()

            if usuario is None:
                if not dry_run:
                    usuario = Usuario(
                        email=email,
                        nome=g.nome,
                        senha_hash=hash_password(_SENHA_PADRAO),
                        is_admin=False,
                        ativo=True,
                    )
                    session.add(usuario)
                    session.flush()
                print(f"  CREATE usuario {email}")
                criados += 1
            else:
                print(f"  EXISTS usuario {email} (id={usuario.id})")

            if dry_run:
                print(f"  WOULD link {len(clientes_ativos)} clientes → {email}")
                continue

            for c in clientes_ativos:
                stmt = pg_insert(UsuarioCliente).values(
                    usuario_id=usuario.id,
                    cliente_id=c.id,
                ).on_conflict_do_nothing()
                result = session.execute(stmt)
                vinculos += result.rowcount or 0

        if not dry_run:
            session.commit()

    print(f"\nResumo: {criados} usuários criados, {vinculos} vínculos inseridos")
    if dry_run:
        print("(dry-run — nenhuma alteração foi salva)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)

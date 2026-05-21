"""One-time script: creates the first admin user.

Usage (run from project root):
    python web/backend/scripts/seed_admin.py --email admin@agencia.com --nome "Admin" --senha "changeme"
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.auth import hash_password
from db import SessionLocal
from models import Usuario
from sqlalchemy import select


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria o primeiro admin do painel de gestores")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nome", required=True)
    parser.add_argument("--senha", required=True)
    args = parser.parse_args()

    with SessionLocal() as session:
        existing = session.execute(select(Usuario).where(Usuario.email == args.email)).scalar_one_or_none()
        if existing:
            print(f"Usuário {args.email!r} já existe (id={existing.id})")
            sys.exit(0)

        user = Usuario(
            email=args.email,
            nome=args.nome,
            senha_hash=hash_password(args.senha),
            is_admin=True,
            ativo=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        print(f"Admin criado: id={user.id} email={user.email}")


if __name__ == "__main__":
    main()

"""add_cnpj_to_cup_clientes

Revision ID: a1cd4eb9b5c1
Revises: f3a1b2c4d5e6
Create Date: 2026-05-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1cd4eb9b5c1"
down_revision: Union[str, None] = "f3a1b2c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotente: em produção a coluna já existe (populada por pipeline externo);
    # em dev/local cria. Sem índice — tabela tem ~1k linhas.
    op.execute("ALTER TABLE staging.cup_clientes ADD COLUMN IF NOT EXISTS cnpj text")


def downgrade() -> None:
    op.execute("ALTER TABLE staging.cup_clientes DROP COLUMN IF EXISTS cnpj")

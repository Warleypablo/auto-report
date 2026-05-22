"""add_gestor_to_clientes

Revision ID: a654ab44e4cb
Revises: d97ddcec2df1
Create Date: 2026-05-21 20:19:59.665782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a654ab44e4cb'
down_revision: Union[str, Sequence[str], None] = 'd97ddcec2df1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clientes", sa.Column("gestor", sa.String(), nullable=True))
    op.create_index("ix_clientes_gestor", "clientes", ["gestor"])


def downgrade() -> None:
    op.drop_index("ix_clientes_gestor", table_name="clientes")
    op.drop_column("clientes", "gestor")

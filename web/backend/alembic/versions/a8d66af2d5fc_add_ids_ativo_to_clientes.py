"""add_ids_ativo_to_clientes

Revision ID: a8d66af2d5fc
Revises: a654ab44e4cb
Create Date: 2026-05-21 21:06:33.154011

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d66af2d5fc'
down_revision: Union[str, Sequence[str], None] = 'a654ab44e4cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clientes", sa.Column("id_google_ads", sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("id_meta_ads",   sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("id_ga4",        sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("painel_url",    sa.String(), nullable=True))
    op.add_column("clientes", sa.Column("pasta_url",     sa.String(), nullable=True))
    op.add_column(
        "clientes",
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("clientes", "ativo")
    op.drop_column("clientes", "pasta_url")
    op.drop_column("clientes", "painel_url")
    op.drop_column("clientes", "id_ga4")
    op.drop_column("clientes", "id_meta_ads")
    op.drop_column("clientes", "id_google_ads")

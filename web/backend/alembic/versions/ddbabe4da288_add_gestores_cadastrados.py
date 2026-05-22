"""add_gestores_cadastrados

Revision ID: ddbabe4da288
Revises: a8d66af2d5fc
Create Date: 2026-05-21 22:05:50.732823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddbabe4da288'
down_revision: Union[str, Sequence[str], None] = 'a8d66af2d5fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gestores_cadastrados",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nome", sa.String(), nullable=False, unique=True),
        sa.Column("squad", sa.String(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("gestores_cadastrados")

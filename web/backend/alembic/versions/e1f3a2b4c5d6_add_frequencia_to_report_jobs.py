"""add_frequencia_to_report_jobs

Revision ID: e1f3a2b4c5d6
Revises: ddbabe4da288
Create Date: 2026-05-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1f3a2b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'ddbabe4da288'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'report_jobs',
        sa.Column('frequencia', sa.String(10), nullable=False, server_default='MENSAL'),
    )


def downgrade() -> None:
    op.drop_column('report_jobs', 'frequencia')

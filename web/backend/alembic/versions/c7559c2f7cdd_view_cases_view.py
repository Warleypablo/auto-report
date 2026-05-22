"""view: cases_view

Revision ID: c7559c2f7cdd
Revises: 6a0518ec0d86
Create Date: 2026-05-20 12:08:23.801549

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7559c2f7cdd'
down_revision: Union[str, Sequence[str], None] = '6a0518ec0d86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CREATE_VIEW = """
CREATE OR REPLACE VIEW cases_view AS
WITH ultimo_snapshot AS (
    SELECT DISTINCT ON (cliente_id)
        cliente_id,
        id AS snapshot_id,
        periodo_inicio,
        periodo_fim,
        frequencia,
        data_coleta,
        faturamento,
        investimento,
        roas,
        cpa,
        leads,
        vendas,
        faturamento_var_pct,
        roas_var_pct,
        metricas_detalhadas
    FROM snapshots
    ORDER BY cliente_id, periodo_fim DESC, data_coleta DESC
)
SELECT
    c.id            AS cliente_id,
    c.slug,
    c.nome,
    c.logo_url,
    c.categoria,
    c.setor,
    c.porte,
    c.descricao_publica,
    c.destaque,
    s.snapshot_id,
    s.periodo_inicio,
    s.periodo_fim,
    s.frequencia,
    s.data_coleta,
    s.faturamento,
    s.investimento,
    s.roas,
    s.cpa,
    s.leads,
    s.vendas,
    s.faturamento_var_pct,
    s.roas_var_pct,
    s.metricas_detalhadas
FROM clientes c
JOIN ultimo_snapshot s ON s.cliente_id = c.id
WHERE c.publicar_vitrine = TRUE;
"""

DROP_VIEW = "DROP VIEW IF EXISTS cases_view;"


def upgrade() -> None:
    op.execute(CREATE_VIEW)


def downgrade() -> None:
    op.execute(DROP_VIEW)

"""add_cup_task_id_and_staging_view

Revision ID: f3a1b2c4d5e6
Revises: e1f3a2b4c5d6
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f3a1b2c4d5e6"
down_revision: Union[str, None] = "e1f3a2b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Coluna de vínculo com ClickUp
    op.add_column(
        "clientes",
        sa.Column("cup_task_id", sa.String(), nullable=True),
    )

    # 2. Popular automaticamente pelo match de nome
    op.execute("""
        UPDATE clientes c
        SET cup_task_id = cc.task_id
        FROM staging.cup_clientes cc
        WHERE LOWER(TRIM(c.nome)) = LOWER(TRIM(cc.nome))
          AND c.cup_task_id IS NULL
    """)

    # 3. View enriquecida: clientes + dados ClickUp + contrato ativo
    op.execute("""
        CREATE OR REPLACE VIEW v_clientes_cup AS
        SELECT
            c.id,
            c.slug,
            c.nome,
            c.categoria,
            c.setor,
            c.gestor,
            c.ativo,
            c.publicar_vitrine,
            c.cup_task_id,
            cc.status             AS cup_status,
            cc.responsavel        AS cup_responsavel,
            cc.responsavel_geral  AS cup_responsavel_geral,
            cc.vendedor           AS cup_vendedor,
            cc.squad              AS cup_squad,
            cc.segmento           AS cup_segmento,
            cc.cluster            AS cup_cluster,
            cc.status_conta       AS cup_status_conta,
            cc.motivo_cancelamento AS cup_motivo_cancelamento,
            -- contrato mais recente ativo/vigente
            ct.id_subtask         AS contrato_id,
            ct.servico            AS contrato_servico,
            ct.produto            AS contrato_produto,
            ct.plano              AS contrato_plano,
            ct.valorr             AS contrato_valor_recorrente,
            ct.valorp             AS contrato_valor_projeto,
            ct.data_inicio        AS contrato_inicio,
            ct.data_encerramento  AS contrato_encerramento,
            ct.status             AS contrato_status
        FROM clientes c
        LEFT JOIN staging.cup_clientes cc
            ON c.cup_task_id = cc.task_id
        LEFT JOIN LATERAL (
            SELECT *
            FROM staging.cup_contratos ct2
            WHERE ct2.id_task = cc.task_id
            ORDER BY ct2.data_inicio DESC NULLS LAST
            LIMIT 1
        ) ct ON TRUE
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_clientes_cup")
    op.drop_column("clientes", "cup_task_id")

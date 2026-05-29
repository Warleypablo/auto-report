"""add_criativos_ad_insights_gestor_travado

Revision ID: b1c2d3e4f5a6
Revises: f79fffd5b218
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'f79fffd5b218'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Nova coluna em clientes
    op.add_column(
        "clientes",
        sa.Column("gestor_travado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 2) Tipos Enum Postgres (rede_anuncio compartilhado entre criativos e ad_insights)
    rede_enum = postgresql.ENUM("META", "GOOGLE", name="rede_anuncio")
    thumb_enum = postgresql.ENUM("pendente", "ok", "sem_imagem", "erro", name="thumb_status")
    rede_enum.create(op.get_bind(), checkfirst=True)
    thumb_enum.create(op.get_bind(), checkfirst=True)

    # 3) criativos
    op.create_table(
        "criativos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cliente_id", sa.UUID(), nullable=False),
        sa.Column(
            "rede",
            postgresql.ENUM("META", "GOOGLE", name="rede_anuncio", create_type=False),
            nullable=False,
        ),
        sa.Column("ad_id", sa.String(), nullable=False),
        sa.Column("nome", sa.String(), nullable=True),
        sa.Column("tipo", sa.String(), nullable=True),
        sa.Column("preview_link", sa.Text(), nullable=True),
        sa.Column(
            "thumb_status",
            postgresql.ENUM(
                "pendente", "ok", "sem_imagem", "erro", name="thumb_status", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("primeiro_dia", sa.Date(), nullable=True),
        sa.Column("ultimo_dia", sa.Date(), nullable=True),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cliente_id", "rede", "ad_id", name="uq_criativo_cliente_rede_ad"),
    )
    op.create_index(op.f("ix_criativos_cliente_id"), "criativos", ["cliente_id"], unique=False)
    op.create_index("ix_criativos_cliente_rede", "criativos", ["cliente_id", "rede"], unique=False)

    # 4) criativo_thumbs
    op.create_table(
        "criativo_thumbs",
        sa.Column("criativo_id", sa.UUID(), nullable=False),
        sa.Column("conteudo", sa.LargeBinary(), nullable=False),
        sa.Column("mime", sa.String(), nullable=False),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["criativo_id"], ["criativos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("criativo_id"),
    )

    # 5) ad_insights
    op.create_table(
        "ad_insights",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cliente_id", sa.UUID(), nullable=False),
        sa.Column(
            "rede",
            postgresql.ENUM("META", "GOOGLE", name="rede_anuncio", create_type=False),
            nullable=False,
        ),
        sa.Column("ad_id", sa.String(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("investimento", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("faturamento", sa.Numeric(20, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("conversoes", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("leads", sa.Integer(), nullable=True),
        sa.Column("impressoes", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("video_3s", sa.Integer(), nullable=True),
        sa.Column("reach", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cliente_id", "rede", "ad_id", "dia", name="uq_ad_insight_cliente_rede_ad_dia"
        ),
    )
    op.create_index(op.f("ix_ad_insights_cliente_id"), "ad_insights", ["cliente_id"], unique=False)
    op.create_index(
        "ix_ad_insights_cliente_dia", "ad_insights", ["cliente_id", "dia"], unique=False
    )
    op.create_index(
        "ix_ad_insights_cliente_rede_dia",
        "ad_insights",
        ["cliente_id", "rede", "dia"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ad_insights_cliente_rede_dia", table_name="ad_insights")
    op.drop_index("ix_ad_insights_cliente_dia", table_name="ad_insights")
    op.drop_index(op.f("ix_ad_insights_cliente_id"), table_name="ad_insights")
    op.drop_table("ad_insights")

    op.drop_table("criativo_thumbs")

    op.drop_index("ix_criativos_cliente_rede", table_name="criativos")
    op.drop_index(op.f("ix_criativos_cliente_id"), table_name="criativos")
    op.drop_table("criativos")

    op.drop_column("clientes", "gestor_travado")

    thumb_enum = postgresql.ENUM("pendente", "ok", "sem_imagem", "erro", name="thumb_status")
    rede_enum = postgresql.ENUM("META", "GOOGLE", name="rede_anuncio")
    thumb_enum.drop(op.get_bind(), checkfirst=True)
    rede_enum.drop(op.get_bind(), checkfirst=True)

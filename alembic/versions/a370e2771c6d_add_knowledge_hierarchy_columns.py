"""add knowledge hierarchy columns

Revision ID: a370e2771c6d
Revises: a1b2c3d4e5f6
Create Date: 2026-04-09 15:05:05.413910

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a370e2771c6d'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add knowledge hierarchy columns and concept_big_concept_map table."""
    # ConceptGraphNode 新增列 + knowledge_level 扩容（String(4)→String(10)）
    # 用 batch_alter_table 包装以兼容 SQLite（SQLite 不支持独立 ALTER COLUMN TYPE）
    with op.batch_alter_table("concept_graph_nodes") as batch_op:
        batch_op.add_column(sa.Column("subject", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("node_type", sa.String(20), nullable=False, server_default="concept"))
        batch_op.add_column(sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("review_status", sa.String(20), nullable=True))
        batch_op.add_column(sa.Column("reviewed_by", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("aliases_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("evidence_ids_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("difficulty", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("bloom_level", sa.String(20), nullable=True))
        batch_op.alter_column("knowledge_level",
                              type_=sa.String(10), existing_type=sa.String(4))

    # ConceptBigConceptMap 表
    op.create_table(
        "concept_big_concept_map",
        sa.Column("concept_id", sa.String(64), sa.ForeignKey("concept_graph_nodes.id"), primary_key=True),
        sa.Column("big_concept_id", sa.String(64), sa.ForeignKey("concept_graph_nodes.id"), primary_key=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    """Remove knowledge hierarchy columns and concept_big_concept_map table."""
    op.drop_table("concept_big_concept_map")

    # 用 batch_alter_table 包装以兼容 SQLite（drop_column + alter_column）
    with op.batch_alter_table("concept_graph_nodes") as batch_op:
        batch_op.drop_column("bloom_level")
        batch_op.drop_column("difficulty")
        batch_op.drop_column("evidence_ids_json")
        batch_op.drop_column("aliases_json")
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by")
        batch_op.drop_column("review_status")
        batch_op.drop_column("display_order")
        batch_op.drop_column("node_type")
        batch_op.drop_column("subject")
        batch_op.alter_column("knowledge_level",
                              type_=sa.String(4), existing_type=sa.String(10))

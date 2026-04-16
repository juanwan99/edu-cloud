"""add_edge_review_status

Revision ID: 2a40f59215de
Revises: a370e2771c6d
Create Date: 2026-04-10 08:20:27.742486

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a40f59215de'
down_revision: Union[str, Sequence[str], None] = 'a370e2771c6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add review_status column to concept_graph_edges."""
    op.add_column(
        "concept_graph_edges",
        sa.Column("review_status", sa.String(20), server_default="ai_draft"),
    )


def downgrade() -> None:
    """Remove review_status column from concept_graph_edges."""
    # 用 batch_alter_table 包装以兼容 SQLite（drop_column）
    with op.batch_alter_table("concept_graph_edges") as batch_op:
        batch_op.drop_column("review_status")

"""add_edge_evidence_and_node_course_code

Revision ID: 51c91f4d98e8
Revises: d8e2f4a1b3c5
Create Date: 2026-05-04 07:10:24.424712

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '51c91f4d98e8'
down_revision: Union[str, Sequence[str], None] = 'd8e2f4a1b3c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add evidence/pedagogical_use to concept_graph_edges, course_code to concept_graph_nodes."""
    op.add_column('concept_graph_edges', sa.Column('evidence', sa.Text(), nullable=True))
    op.add_column('concept_graph_edges', sa.Column('pedagogical_use', sa.String(length=30), nullable=True))
    op.add_column('concept_graph_nodes', sa.Column('course_code', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_concept_graph_nodes_course_code'), 'concept_graph_nodes', ['course_code'], unique=False)


def downgrade() -> None:
    """Reverse: drop evidence/pedagogical_use from edges, course_code from nodes."""
    op.drop_index(op.f('ix_concept_graph_nodes_course_code'), table_name='concept_graph_nodes')
    op.drop_column('concept_graph_nodes', 'course_code')
    op.drop_column('concept_graph_edges', 'pedagogical_use')
    op.drop_column('concept_graph_edges', 'evidence')

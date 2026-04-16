"""add concept_stats table

Revision ID: 46b200fa9704
Revises: 52af1c37bf14
Create Date: 2026-04-13 08:42:39.212158

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46b200fa9704'
down_revision: Union[str, Sequence[str], None] = '52af1c37bf14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'concept_stats',
        sa.Column('concept_id', sa.String(length=64), nullable=False),
        sa.Column('exam_frequency', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('exam_coverage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('avg_difficulty', sa.Float(), nullable=True),
        sa.Column('importance_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('planning_weight', sa.JSON(), nullable=True),
        sa.Column('textbook_chapters', sa.JSON(), nullable=False),
        sa.Column('study_unit_id', sa.String(length=64), nullable=True),
        sa.Column('estimated_minutes', sa.Integer(), nullable=True),
        sa.Column('prerequisite_depth', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['concept_id'], ['concept_graph_nodes.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('concept_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('concept_stats')

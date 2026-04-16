"""add knowledge tree tables

Revision ID: a1b2c3d4e5f6
Revises: 30da2c2e9aa6
Create Date: 2026-04-07 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '30da2c2e9aa6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'concept_graph_nodes',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('knowledge_level', sa.String(4), nullable=False),
        sa.Column('primary_module', sa.String(10), nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('synced_at', sa.DateTime, nullable=False),
    )

    op.create_table(
        'concept_graph_edges',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('source_id', sa.String(64), sa.ForeignKey('concept_graph_nodes.id'), nullable=False, index=True),
        sa.Column('target_id', sa.String(64), sa.ForeignKey('concept_graph_nodes.id'), nullable=False, index=True),
        sa.Column('relation_type', sa.String(30), nullable=False),
        sa.Column('strength', sa.Float, server_default='1.0'),
        sa.Column('confidence', sa.Float, server_default='1.0'),
        sa.Column('synced_at', sa.DateTime, nullable=False),
        sa.UniqueConstraint('source_id', 'target_id', 'relation_type'),
    )

    op.create_table(
        'edit_sync_failures',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('operation_json', sa.Text, nullable=False),
        sa.Column('error_message', sa.Text, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('edit_sync_failures')
    op.drop_table('concept_graph_edges')
    op.drop_table('concept_graph_nodes')

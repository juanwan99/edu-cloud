"""add entity_memory and project_state tables

Revision ID: 1a325e38e941
Revises: d5b8da9e0931
Create Date: 2026-04-05 17:08:07.436342

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a325e38e941'
down_revision: Union[str, Sequence[str], None] = 'd5b8da9e0931'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'entity_memory',
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False),
        sa.Column('school_id', sa.String(36), nullable=False),
        sa.Column('facts', sa.JSON(), nullable=True),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'school_id', 'entity_type', 'entity_id',
            name='uq_entity_memory_lookup',
        ),
    )
    op.create_index(
        'ix_entity_memory_lookup',
        'entity_memory',
        ['school_id', 'entity_type', 'entity_id'],
        unique=False,
    )

    op.create_table(
        'project_state',
        sa.Column('project_type', sa.String(30), nullable=False),
        sa.Column('project_id', sa.String(36), nullable=False),
        sa.Column('owner_id', sa.String(36), nullable=False),
        sa.Column('school_id', sa.String(36), nullable=False),
        sa.Column('state', sa.JSON(), nullable=True),
        sa.Column('checkpoints', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'project_type', 'project_id',
            name='uq_project_state_project',
        ),
    )
    op.create_index(
        'ix_project_state_owner',
        'project_state',
        ['owner_id', 'school_id'],
        unique=False,
    )
    op.create_index(
        'ix_project_state_lookup',
        'project_state',
        ['project_type', 'project_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_project_state_lookup', table_name='project_state')
    op.drop_index('ix_project_state_owner', table_name='project_state')
    op.drop_table('project_state')

    op.drop_index('ix_entity_memory_lookup', table_name='entity_memory')
    op.drop_table('entity_memory')

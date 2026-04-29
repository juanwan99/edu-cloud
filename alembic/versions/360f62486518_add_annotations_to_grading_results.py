"""add annotations to grading_results

Revision ID: 360f62486518
Revises: 3ab6982f3aef
Create Date: 2026-04-29 22:26:20.995176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '360f62486518'
down_revision: Union[str, Sequence[str], None] = '3ab6982f3aef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('grading_results', sa.Column('annotations', sa.JSON(), nullable=True))
    op.add_column('grading_tasks', sa.Column('use_vision', sa.Boolean(), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    op.drop_column('grading_tasks', 'use_vision')
    op.drop_column('grading_results', 'annotations')

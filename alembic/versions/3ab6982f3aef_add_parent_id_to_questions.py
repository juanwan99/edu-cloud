"""add parent_id to questions

Revision ID: 3ab6982f3aef
Revises: 0ef7a0f54171
Create Date: 2026-04-29 10:24:07.027779

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ab6982f3aef'
down_revision: Union[str, Sequence[str], None] = '0ef7a0f54171'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('questions', sa.Column('parent_id', sa.String(length=36), nullable=True))
    op.create_index(op.f('ix_questions_parent_id'), 'questions', ['parent_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_questions_parent_id'), table_name='questions')
    op.drop_column('questions', 'parent_id')

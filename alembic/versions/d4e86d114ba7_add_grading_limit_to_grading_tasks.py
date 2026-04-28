"""add grading_limit to grading_tasks

Revision ID: d4e86d114ba7
Revises: d025636505a0
Create Date: 2026-04-28 14:44:51.297435

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e86d114ba7'
down_revision: Union[str, Sequence[str], None] = 'd025636505a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('grading_tasks', sa.Column('grading_limit', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('grading_tasks', 'grading_limit')

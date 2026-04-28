"""add grading_mode to grading_tasks

Revision ID: 0ef7a0f54171
Revises: d4e86d114ba7
Create Date: 2026-04-28 22:01:10.636340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ef7a0f54171'
down_revision: Union[str, Sequence[str], None] = 'd4e86d114ba7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'grading_tasks',
        sa.Column('grading_mode', sa.String(length=20), nullable=False, server_default='realtime'),
    )


def downgrade() -> None:
    op.drop_column('grading_tasks', 'grading_mode')

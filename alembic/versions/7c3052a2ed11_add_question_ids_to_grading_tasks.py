"""add question_ids to grading_tasks

Revision ID: 7c3052a2ed11
Revises: 360f62486518
Create Date: 2026-05-02 21:38:35.951913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c3052a2ed11'
down_revision: Union[str, Sequence[str], None] = '360f62486518'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('grading_tasks', sa.Column('question_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('grading_tasks', 'question_ids')

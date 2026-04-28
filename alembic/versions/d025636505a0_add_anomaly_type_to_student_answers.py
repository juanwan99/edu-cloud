"""add anomaly_type to student_answers

Revision ID: d025636505a0
Revises: e608ef1086b4
Create Date: 2026-04-28 09:20:57.735139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd025636505a0'
down_revision: Union[str, Sequence[str], None] = 'e608ef1086b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('student_answers', sa.Column('anomaly_type', sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column('student_answers', 'anomaly_type')

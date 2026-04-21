"""add student id_card

Revision ID: 45c9d83d780e
Revises: 1085b71343ee
Create Date: 2026-04-19

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '45c9d83d780e'
down_revision: Union[str, Sequence[str], None] = '1085b71343ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('students', sa.Column('id_card', sa.String(length=18), nullable=True))


def downgrade() -> None:
    op.drop_column('students', 'id_card')

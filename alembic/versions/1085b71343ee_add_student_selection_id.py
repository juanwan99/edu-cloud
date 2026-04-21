"""add student selection_id

Revision ID: 1085b71343ee
Revises: e6a921f4b8c0
Create Date: 2026-04-19 20:20:34.268434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1085b71343ee'
down_revision: Union[str, Sequence[str], None] = 'e6a921f4b8c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('students', sa.Column('selection_id', sa.String(length=36), nullable=True))
    with op.batch_alter_table('students') as batch_op:
        batch_op.create_foreign_key(
            'fk_student_selection', 'subject_selections', ['selection_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('students') as batch_op:
        batch_op.drop_constraint('fk_student_selection', type_='foreignkey')
    op.drop_column('students', 'selection_id')

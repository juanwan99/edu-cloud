"""add question content and grading task question_id

Revision ID: e241e1568792
Revises: 874f6f9c14cc
Create Date: 2026-04-23 06:53:41.370904

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e241e1568792'
down_revision: Union[str, Sequence[str], None] = '874f6f9c14cc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add content fields to questions table
    with op.batch_alter_table('questions') as batch_op:
        batch_op.add_column(sa.Column('content', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('content_images', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('reference_answer', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('reference_answer_images', sa.JSON(), nullable=True))

    # Add question_id to grading_tasks table
    with op.batch_alter_table('grading_tasks') as batch_op:
        batch_op.add_column(sa.Column('question_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_grading_tasks_question_id',
            'questions',
            ['question_id'],
            ['id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('grading_tasks') as batch_op:
        batch_op.drop_constraint('fk_grading_tasks_question_id', type_='foreignkey')
        batch_op.drop_column('question_id')

    with op.batch_alter_table('questions') as batch_op:
        batch_op.drop_column('reference_answer_images')
        batch_op.drop_column('reference_answer')
        batch_op.drop_column('content_images')
        batch_op.drop_column('content')


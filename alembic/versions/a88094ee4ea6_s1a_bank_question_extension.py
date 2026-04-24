"""s1a_bank_question_extension

Revision ID: a88094ee4ea6
Revises: a8c7d2e4f135
Create Date: 2026-04-24 18:11:29.812374

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a88094ee4ea6'
down_revision: Union[str, Sequence[str], None] = 'a8c7d2e4f135'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """S1-A: bank_questions 扩展 5 字段（source / explanation / knowledge_point_ids / difficulty_level / grade_id）。

    refs: docs/plans/2026-04-24-haofenshu-s1-bank-plan.md Task 2
    refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverable 1.1
    ORC-S1A-003: 只加不改；ORC-S1A-004: sa.JSON() 双方言兼容
    """
    with op.batch_alter_table('bank_questions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('explanation', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('knowledge_point_ids', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('difficulty_level', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('grade_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    """S1-A downgrade: 移除 5 新字段。无数据保留（5 列全 nullable 无默认值）。"""
    with op.batch_alter_table('bank_questions', schema=None) as batch_op:
        batch_op.drop_column('grade_id')
        batch_op.drop_column('difficulty_level')
        batch_op.drop_column('knowledge_point_ids')
        batch_op.drop_column('explanation')
        batch_op.drop_column('source')

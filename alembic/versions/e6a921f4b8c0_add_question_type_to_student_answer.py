"""add question_type to student_answers

Revision ID: e6a921f4b8c0
Revises: d4f1c8a92e75
Create Date: 2026-04-16

Phase 1-C：StudentAnswer 表新增 question_type 列，paper-seg 上传切图时
携带（choice/multi_choice/fill_blank/essay），workers/grading.py 据此
为 LLM 选 prompt（fill_blank 短答 / essay 长答）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6a921f4b8c0'
down_revision: Union[str, Sequence[str], None] = 'd4f1c8a92e75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('student_answers') as batch_op:
        batch_op.add_column(sa.Column('question_type', sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('student_answers') as batch_op:
        batch_op.drop_column('question_type')

"""add grading_pipeline_logs table

Revision ID: e608ef1086b4
Revises: b9d8e3f5a246
Create Date: 2026-04-27 16:49:27.471353

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e608ef1086b4'
down_revision: Union[str, Sequence[str], None] = 'b9d8e3f5a246'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('grading_pipeline_logs',
    sa.Column('answer_id', sa.String(length=36), nullable=False),
    sa.Column('question_id', sa.String(length=36), nullable=False),
    sa.Column('task_id', sa.String(length=36), nullable=True),
    sa.Column('school_id', sa.String(length=36), nullable=False),
    sa.Column('subject_code', sa.String(length=20), nullable=True),
    sa.Column('question_type', sa.String(length=20), nullable=True),
    sa.Column('pipeline_type', sa.String(length=20), nullable=False),
    sa.Column('image_size_bytes', sa.Integer(), nullable=True),
    sa.Column('is_blank', sa.Boolean(), nullable=False),
    sa.Column('ocr_model', sa.String(length=100), nullable=True),
    sa.Column('ocr_prompt_type', sa.String(length=50), nullable=True),
    sa.Column('ocr_ms', sa.Integer(), nullable=True),
    sa.Column('ocr_text', sa.Text(), nullable=True),
    sa.Column('ocr_blanks_count', sa.Integer(), nullable=True),
    sa.Column('char_count', sa.Integer(), nullable=True),
    sa.Column('grading_model', sa.String(length=100), nullable=True),
    sa.Column('grading_prompt_type', sa.String(length=50), nullable=True),
    sa.Column('grading_ms', sa.Integer(), nullable=True),
    sa.Column('total_ms', sa.Integer(), nullable=True),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('error_type', sa.String(length=50), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['answer_id'], ['student_answers.id'], ),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['grading_tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_grading_pipeline_logs_answer_id'), 'grading_pipeline_logs', ['answer_id'], unique=False)
    op.create_index('ix_pipeline_log_question', 'grading_pipeline_logs', ['question_id'], unique=False)
    op.create_index('ix_pipeline_log_school', 'grading_pipeline_logs', ['school_id'], unique=False)
    op.create_index('ix_pipeline_log_task', 'grading_pipeline_logs', ['task_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_pipeline_log_task', table_name='grading_pipeline_logs')
    op.drop_index('ix_pipeline_log_school', table_name='grading_pipeline_logs')
    op.drop_index('ix_pipeline_log_question', table_name='grading_pipeline_logs')
    op.drop_index(op.f('ix_grading_pipeline_logs_answer_id'), table_name='grading_pipeline_logs')
    op.drop_table('grading_pipeline_logs')

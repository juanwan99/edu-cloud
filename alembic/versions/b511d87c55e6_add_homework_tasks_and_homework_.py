"""add homework_tasks and homework_submissions tables

Revision ID: b511d87c55e6
Revises: c9587c787c6b
Create Date: 2026-03-30 19:31:12.105036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b511d87c55e6'
down_revision: Union[str, Sequence[str], None] = 'c9587c787c6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'homework_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('school_id', sa.String(36), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('task_type', sa.String(20), nullable=False, server_default='regular'),
        sa.Column('subject_code', sa.String(20), nullable=False),
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id'), nullable=True),
        sa.Column('assigned_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('exam_id', sa.String(36), sa.ForeignKey('exams.id'), nullable=True),
        sa.Column('deadline', sa.DateTime, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('grading_mode', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_hw_task_school_status', 'homework_tasks', ['school_id', 'status'])
    op.create_index('ix_hw_task_school_class', 'homework_tasks', ['school_id', 'class_id'])
    op.create_index('ix_hw_task_assigned_by', 'homework_tasks', ['assigned_by'])

    op.create_table(
        'homework_submissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('homework_tasks.id'), nullable=False),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('score', sa.Float, nullable=True),
        sa.Column('feedback', sa.Text, nullable=True),
        sa.Column('submit_time', sa.DateTime, nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('graded_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('graded_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.UniqueConstraint('task_id', 'student_id', name='uq_hw_submission_task_student'),
    )
    op.create_index('ix_hw_sub_task_status', 'homework_submissions', ['task_id', 'status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('homework_submissions')
    op.drop_table('homework_tasks')

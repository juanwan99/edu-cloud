"""add grading_assignments and grading_quality_checks tables

Revision ID: 2cde4b537c7b
Revises: 4c337d512d00
Create Date: 2026-03-30 12:40:37.602930

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2cde4b537c7b'
down_revision: Union[str, Sequence[str], None] = '4c337d512d00'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('grading_assignments',
    sa.Column('exam_id', sa.String(length=36), nullable=False),
    sa.Column('subject_id', sa.String(length=36), nullable=False),
    sa.Column('question_ids', sa.JSON(), nullable=False),
    sa.Column('assigned_to', sa.String(length=36), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('graded_count', sa.Integer(), nullable=False),
    sa.Column('total_count', sa.Integer(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('school_id', sa.String(length=36), nullable=False),
    sa.Column('is_second_grading', sa.Boolean(), nullable=False),
    sa.Column('paired_assignment_id', sa.String(length=36), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ),
    sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ),
    sa.ForeignKeyConstraint(['paired_assignment_id'], ['grading_assignments.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_assignment_exam_teacher', 'grading_assignments', ['exam_id', 'assigned_to'], unique=False)
    op.create_index(op.f('ix_grading_assignments_assigned_to'), 'grading_assignments', ['assigned_to'], unique=False)
    op.create_index(op.f('ix_grading_assignments_exam_id'), 'grading_assignments', ['exam_id'], unique=False)
    op.create_index(op.f('ix_grading_assignments_school_id'), 'grading_assignments', ['school_id'], unique=False)
    op.create_index(op.f('ix_grading_assignments_subject_id'), 'grading_assignments', ['subject_id'], unique=False)
    op.create_table('grading_quality_checks',
    sa.Column('exam_id', sa.String(length=36), nullable=False),
    sa.Column('subject_id', sa.String(length=36), nullable=False),
    sa.Column('question_id', sa.String(length=36), nullable=False),
    sa.Column('check_type', sa.String(length=20), nullable=False),
    sa.Column('original_result_id', sa.String(length=36), nullable=True),
    sa.Column('original_grader_id', sa.String(length=36), nullable=True),
    sa.Column('checker_id', sa.String(length=36), nullable=True),
    sa.Column('original_score', sa.Float(), nullable=False),
    sa.Column('check_score', sa.Float(), nullable=True),
    sa.Column('deviation', sa.Float(), nullable=True),
    sa.Column('severity', sa.String(length=10), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('school_id', sa.String(length=36), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ),
    sa.ForeignKeyConstraint(['original_result_id'], ['ai_grading_results.id'], ),
    sa.ForeignKeyConstraint(['question_id'], ['questions.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_grading_quality_checks_exam_id'), 'grading_quality_checks', ['exam_id'], unique=False)
    op.create_index(op.f('ix_grading_quality_checks_school_id'), 'grading_quality_checks', ['school_id'], unique=False)
    op.create_index(op.f('ix_grading_quality_checks_subject_id'), 'grading_quality_checks', ['subject_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_grading_quality_checks_subject_id'), table_name='grading_quality_checks')
    op.drop_index(op.f('ix_grading_quality_checks_school_id'), table_name='grading_quality_checks')
    op.drop_index(op.f('ix_grading_quality_checks_exam_id'), table_name='grading_quality_checks')
    op.drop_table('grading_quality_checks')
    op.drop_index(op.f('ix_grading_assignments_subject_id'), table_name='grading_assignments')
    op.drop_index(op.f('ix_grading_assignments_school_id'), table_name='grading_assignments')
    op.drop_index(op.f('ix_grading_assignments_exam_id'), table_name='grading_assignments')
    op.drop_index(op.f('ix_grading_assignments_assigned_to'), table_name='grading_assignments')
    op.drop_index('ix_assignment_exam_teacher', table_name='grading_assignments')
    op.drop_table('grading_assignments')

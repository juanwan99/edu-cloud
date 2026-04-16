"""add menu_configs and analysis tables + exam_results rank fields

Revision ID: 52af1c37bf14
Revises: c0ndc7a6b1e5
Create Date: 2026-04-13 07:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '52af1c37bf14'
down_revision: Union[str, Sequence[str], None] = 'c0ndc7a6b1e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'menu_configs',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('code', sa.String(32), nullable=False),
        sa.Column('name', sa.String(64), nullable=False),
        sa.Column('icon', sa.String(32), nullable=True),
        sa.Column('sort', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_id', sa.Integer(),
                  sa.ForeignKey('menu_configs.id'), nullable=True),
        sa.Column('path', sa.String(128), nullable=True),
        sa.Column('roles', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('requires_module', sa.String(32), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        'class_analysis',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('exam_id', sa.String(36), sa.ForeignKey('exams.id'), nullable=False),
        sa.Column('subject_id', sa.String(36), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('school_id', sa.String(36), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('avg_score', sa.Numeric(6, 2), nullable=True),
        sa.Column('max_score', sa.Numeric(6, 2), nullable=True),
        sa.Column('min_score', sa.Numeric(6, 2), nullable=True),
        sa.Column('pass_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('excellent_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('student_count', sa.Integer(), nullable=True),
        sa.Column('score_distribution', sa.JSON(), nullable=True),
        sa.Column('common_wrong_questions', sa.JSON(), nullable=True),
        sa.Column('knowledge_mastery', sa.JSON(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint('exam_id', 'subject_id', 'class_id',
                            name='uq_class_analysis'),
    )

    op.create_table(
        'student_analysis',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('exam_id', sa.String(36), sa.ForeignKey('exams.id'), nullable=False),
        sa.Column('school_id', sa.String(36), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('total_score', sa.Numeric(7, 2), nullable=True),
        sa.Column('rank_in_class', sa.Integer(), nullable=True),
        sa.Column('rank_in_grade', sa.Integer(), nullable=True),
        sa.Column('subject_scores', sa.JSON(), nullable=True),
        sa.Column('weak_knowledge', sa.JSON(), nullable=True),
        sa.Column('improvement_trend', sa.JSON(), nullable=True),
        sa.Column('computed_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=True),
        sa.UniqueConstraint('student_id', 'exam_id', name='uq_student_analysis'),
    )

    op.create_table(
        'student_knp_mastery',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('exam_id', sa.String(36), sa.ForeignKey('exams.id'), nullable=False),
        sa.Column('knp_id', sa.String(64), nullable=False),
        sa.Column('school_id', sa.String(36), sa.ForeignKey('schools.id'), nullable=False),
        sa.Column('stu_rate', sa.Numeric(4, 3), nullable=True),
        sa.Column('class_rate', sa.Numeric(4, 3), nullable=True),
        sa.Column('grade_rate', sa.Numeric(4, 3), nullable=True),
        sa.UniqueConstraint('student_id', 'exam_id', 'knp_id',
                            name='uq_student_knp_mastery'),
    )

    op.add_column('exam_results',
                  sa.Column('rank_in_class', sa.Integer(), nullable=True))
    op.add_column('exam_results',
                  sa.Column('rank_in_grade', sa.Integer(), nullable=True))


def downgrade() -> None:
    # 用 batch_alter_table 包装以兼容 SQLite（drop_column）
    with op.batch_alter_table('exam_results') as batch_op:
        batch_op.drop_column('rank_in_grade')
        batch_op.drop_column('rank_in_class')
    op.drop_table('student_knp_mastery')
    op.drop_table('student_analysis')
    op.drop_table('class_analysis')
    op.drop_table('menu_configs')

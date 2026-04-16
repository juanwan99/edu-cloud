"""add_assignments_selections

Revision ID: 2bc5ab4977e5
Revises: b71cef336bfa
Create Date: 2026-03-29 23:07:45.263527

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2bc5ab4977e5'
down_revision: Union[str, Sequence[str], None] = 'b71cef336bfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('subject_selections',
    sa.Column('school_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('subject_codes', sa.JSON(), nullable=False),
    sa.Column('mode', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('school_id', 'name', name='uq_subject_selection_name')
    )
    op.create_index(op.f('ix_subject_selections_school_id'), 'subject_selections', ['school_id'], unique=False)
    op.create_table('teacher_assignments',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('class_id', sa.String(length=36), nullable=False),
    sa.Column('subject_code', sa.String(length=50), nullable=False),
    sa.Column('semester', sa.String(length=20), nullable=False),
    sa.Column('school_id', sa.String(length=36), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], ),
    sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'class_id', 'subject_code', 'semester', name='uq_teacher_assignment')
    )
    op.create_index(op.f('ix_teacher_assignments_class_id'), 'teacher_assignments', ['class_id'], unique=False)
    op.create_index(op.f('ix_teacher_assignments_school_id'), 'teacher_assignments', ['school_id'], unique=False)
    op.create_index(op.f('ix_teacher_assignments_user_id'), 'teacher_assignments', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_teacher_assignments_user_id'), table_name='teacher_assignments')
    op.drop_index(op.f('ix_teacher_assignments_school_id'), table_name='teacher_assignments')
    op.drop_index(op.f('ix_teacher_assignments_class_id'), table_name='teacher_assignments')
    op.drop_table('teacher_assignments')
    op.drop_index(op.f('ix_subject_selections_school_id'), table_name='subject_selections')
    op.drop_table('subject_selections')

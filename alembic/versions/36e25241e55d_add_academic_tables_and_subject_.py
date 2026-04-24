"""add academic tables and subject schedule fields

Revision ID: 36e25241e55d
Revises: e241e1568792
Create Date: 2026-04-24 09:04:58.811205

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36e25241e55d'
down_revision: Union[str, Sequence[str], None] = 'e241e1568792'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'semesters',
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('school_year', sa.String(length=20), nullable=False),
        sa.Column('term', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('school_id', 'school_year', 'term', name='uq_semester'),
    )
    op.create_index(op.f('ix_semesters_school_id'), 'semesters', ['school_id'], unique=False)

    op.create_table(
        'time_periods',
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('semester_id', sa.String(length=36), nullable=False),
        sa.Column('period_number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=20), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('period_type', sa.String(length=20), nullable=False),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.ForeignKeyConstraint(['semester_id'], ['semesters.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('school_id', 'semester_id', 'period_number', name='uq_time_period'),
    )
    op.create_index(op.f('ix_time_periods_school_id'), 'time_periods', ['school_id'], unique=False)

    op.create_table(
        'timetable_slots',
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('semester_id', sa.String(length=36), nullable=False),
        sa.Column('class_id', sa.String(length=36), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=False),
        sa.Column('period_id', sa.String(length=36), nullable=False),
        sa.Column('subject_code', sa.String(length=50), nullable=False),
        sa.Column('teacher_id', sa.String(length=36), nullable=False),
        sa.Column('room', sa.String(length=50), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id']),
        sa.ForeignKeyConstraint(['period_id'], ['time_periods.id']),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id']),
        sa.ForeignKeyConstraint(['semester_id'], ['semesters.id']),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('class_id', 'semester_id', 'weekday', 'period_id', name='uq_timetable_slot'),
    )
    op.create_index(op.f('ix_timetable_slots_class_id'), 'timetable_slots', ['class_id'], unique=False)
    op.create_index(op.f('ix_timetable_slots_school_id'), 'timetable_slots', ['school_id'], unique=False)

    with op.batch_alter_table('subjects') as batch_op:
        batch_op.add_column(sa.Column('exam_start', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('exam_end', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('exam_room', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('proctor_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('subjects') as batch_op:
        batch_op.drop_column('proctor_ids')
        batch_op.drop_column('exam_room')
        batch_op.drop_column('exam_end')
        batch_op.drop_column('exam_start')

    op.drop_index(op.f('ix_timetable_slots_school_id'), table_name='timetable_slots')
    op.drop_index(op.f('ix_timetable_slots_class_id'), table_name='timetable_slots')
    op.drop_table('timetable_slots')

    op.drop_index(op.f('ix_time_periods_school_id'), table_name='time_periods')
    op.drop_table('time_periods')

    op.drop_index(op.f('ix_semesters_school_id'), table_name='semesters')
    op.drop_table('semesters')

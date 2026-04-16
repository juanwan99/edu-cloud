"""add conduct module tables

Revision ID: c0ndc7a6b1e5
Revises: b08103b3a6f5
Create Date: 2026-04-13 06:56:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c0ndc7a6b1e5'
down_revision: Union[str, Sequence[str], None] = 'b08103b3a6f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'student_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'),
                  nullable=False, unique=True),
        sa.Column('avatar', sa.String(10), nullable=True),
        sa.Column('birth_date', sa.Date(), nullable=True),
        sa.Column('ethnicity', sa.String(20), nullable=True),
        sa.Column('id_card_number', sa.Text(), nullable=True),
        sa.Column('blood_type', sa.String(5), nullable=True),
        sa.Column('health_notes', sa.Text(), nullable=True),
        sa.Column('home_address', sa.Text(), nullable=True),
        sa.Column('emergency_contact_name', sa.String(50), nullable=True),
        sa.Column('emergency_contact_phone', sa.String(20), nullable=True),
        sa.Column('verify_code', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'conduct_class_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id'),
                  nullable=False, unique=True),
        sa.Column('invite_code', sa.String(10), nullable=False, unique=True),
        sa.Column('verify_code_type', sa.String(10), nullable=False,
                  server_default='id_card'),
        sa.Column('required_parent_fields', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'conduct_rule_categories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id'), nullable=True),
        sa.Column('school_id', sa.String(36), sa.ForeignKey('schools.id'), nullable=True),
        sa.Column('scope', sa.String(10), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'conduct_rule_items',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.String(36),
                  sa.ForeignKey('conduct_rule_categories.id'), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )

    op.create_table(
        'conduct_semesters',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('school_id', sa.String(36), sa.ForeignKey('schools.id'), nullable=True),
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id'), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'conduct_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('operator_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('source', sa.String(10), nullable=False, server_default='manual'),
        sa.Column('rule_item_id', sa.String(36),
                  sa.ForeignKey('conduct_rule_items.id'), nullable=True),
        sa.Column('semester_id', sa.String(36),
                  sa.ForeignKey('conduct_semesters.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'conduct_groups',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('class_id', sa.String(36), sa.ForeignKey('classes.id'), nullable=False),
        sa.Column('avatar', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('class_id', 'name', name='uq_conduct_group_class_name'),
    )

    op.create_table(
        'conduct_group_members',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('student_id', sa.String(36), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('group_id', sa.String(36), sa.ForeignKey('conduct_groups.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('student_id', 'group_id', name='uq_conduct_group_member'),
    )


def downgrade() -> None:
    op.drop_table('conduct_group_members')
    op.drop_table('conduct_groups')
    op.drop_table('conduct_records')
    op.drop_table('conduct_semesters')
    op.drop_table('conduct_rule_items')
    op.drop_table('conduct_rule_categories')
    op.drop_table('conduct_class_configs')
    op.drop_table('student_profiles')

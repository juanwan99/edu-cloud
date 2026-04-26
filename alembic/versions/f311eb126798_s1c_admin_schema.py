"""s1c_admin_schema

Revision ID: f311eb126798
Revises: a88094ee4ea6
Create Date: 2026-04-24 22:09:35.736451

S1-C: 行政配置 schema（grades 新表 / teaching_plans 新表 / classes.grade_id + FK /
bank_questions.grade_id 类型修正 + FK）。

refs: docs/plans/2026-04-24-haofenshu-s1-admin-plan.md Task 4
refs: docs/plans/2026-04-24-haofenshu-vs-edu-phase2-design.md §4.1 deliverables 1.3/1.4
ORC-S1C-001: linear chain 第 2 环，down_revision='a88094ee4ea6'（S1-A T2 slug）
ORC-S1C-003: teaching_plans FK 仅指向 schools/grades/users（禁 lesson_plans 等未建表）
ORC-S1C-004: 所有 grade_id FK 类型统一 String(36)；bank.grade_id 从 Integer 改 String(36) 闭环 TD-S1A-002
ORC-S1A-004 传承: JSON 用 sa.JSON()，DDL 用 batch_alter_table 保持 SQLite+PG 双方言中立
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f311eb126798'
down_revision: Union[str, Sequence[str], None] = 'a88094ee4ea6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1.3 grades 新表（跨模块共享年级实体）
    op.create_table(
        'grades',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('grade_level', sa.Integer(), nullable=True),
        sa.Column('xueduan', sa.String(length=20), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], name='fk_grades_school_id'),
        sa.UniqueConstraint('school_id', 'name', name='uq_grade_school_name'),
    )

    # 1.4 teaching_plans 新表（ORC-S1C-003: 仅 3 个 FK 指向 schools/grades/users）
    op.create_table(
        'teaching_plans',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('school_id', sa.String(length=36), nullable=False),
        sa.Column('subject_code', sa.String(length=50), nullable=False),
        sa.Column('grade_id', sa.String(length=36), nullable=True),
        sa.Column('semester', sa.String(length=30), nullable=False),
        sa.Column('weeks_json', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], name='fk_teaching_plans_school_id'),
        sa.ForeignKeyConstraint(['grade_id'], ['grades.id'], name='fk_teaching_plans_grade_id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_teaching_plans_created_by'),
        sa.UniqueConstraint(
            'school_id', 'subject_code', 'grade_id', 'semester',
            name='uq_teaching_plan_scope',
        ),
    )

    # 1.3 classes.grade_id + FK（ORC-S1C-002: 守旧 grade/grade_number 不动，只加 1 列）
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('grade_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            'fk_classes_grade_id', 'grades', ['grade_id'], ['id'],
        )

    # TD-S1A-002 闭环: bank_questions.grade_id 类型 Integer → String(36) + FK（ORC-S1C-004）
    with op.batch_alter_table('bank_questions', schema=None) as batch_op:
        batch_op.alter_column(
            'grade_id',
            existing_type=sa.Integer(),
            type_=sa.String(length=36),
            existing_nullable=True,
            postgresql_using='grade_id::text',  # PG 上 Integer→Text 转换（列全 NULL 无实际转换）
        )
        batch_op.create_foreign_key(
            'fk_bank_questions_grade_id', 'grades', ['grade_id'], ['id'],
        )


def downgrade() -> None:
    """S1-C downgrade: LIFO 顺序撤销 upgrade 全部操作。

    依赖顺序：先 drop FK 再 drop 表/列，防止"referencing still active"。
    """
    # TD-S1A-002 反向: bank_questions.grade_id FK 去除 + 类型回 Integer
    with op.batch_alter_table('bank_questions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_bank_questions_grade_id', type_='foreignkey')
        batch_op.alter_column(
            'grade_id',
            existing_type=sa.String(length=36),
            type_=sa.Integer(),
            existing_nullable=True,
            postgresql_using='NULLIF(grade_id, \'\')::integer',  # PG 空字符串→NULL→Integer
        )

    # classes.grade_id FK + 列去除
    with op.batch_alter_table('classes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_classes_grade_id', type_='foreignkey')
        batch_op.drop_column('grade_id')

    # teaching_plans 表去除（LIFO 先于 grades，因为 teaching_plans.grade_id FK 指向 grades）
    op.drop_table('teaching_plans')

    # grades 表去除
    op.drop_table('grades')

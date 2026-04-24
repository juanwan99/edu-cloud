"""conduct: add updated_at columns and FK indexes

Revision ID: a8c7d2e4f135
Revises: 36e25241e55d
Create Date: 2026-04-24

"""
from alembic import op
import sqlalchemy as sa

revision: str = 'a8c7d2e4f135'
down_revision: str = '36e25241e55d'
branch_labels = None
depends_on = None

_NOW = sa.text("(CURRENT_TIMESTAMP)")

_UPDATED_AT_TABLES = [
    "conduct_rule_categories",
    "conduct_rule_items",
    "conduct_records",
    "conduct_groups",
    "conduct_semesters",
]

_FK_INDEXES = [
    ("ix_conduct_rule_categories_class_id", "conduct_rule_categories", ["class_id"]),
    ("ix_conduct_rule_categories_school_id", "conduct_rule_categories", ["school_id"]),
    ("ix_conduct_rule_items_category_id", "conduct_rule_items", ["category_id"]),
    ("ix_conduct_records_student_id", "conduct_records", ["student_id"]),
    ("ix_conduct_records_class_id", "conduct_records", ["class_id"]),
    ("ix_conduct_records_operator_id", "conduct_records", ["operator_id"]),
    ("ix_conduct_records_rule_item_id", "conduct_records", ["rule_item_id"]),
    ("ix_conduct_records_semester_id", "conduct_records", ["semester_id"]),
    ("ix_conduct_groups_class_id", "conduct_groups", ["class_id"]),
    ("ix_conduct_group_members_student_id", "conduct_group_members", ["student_id"]),
    ("ix_conduct_group_members_group_id", "conduct_group_members", ["group_id"]),
    ("ix_conduct_semesters_school_id", "conduct_semesters", ["school_id"]),
    ("ix_conduct_semesters_class_id", "conduct_semesters", ["class_id"]),
]


def upgrade() -> None:
    for table in _UPDATED_AT_TABLES:
        with op.batch_alter_table(table) as batch:
            if table == "conduct_rule_items":
                batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW))
            batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW))

    for ix_name, table, columns in _FK_INDEXES:
        op.create_index(ix_name, table, columns)


def downgrade() -> None:
    for ix_name, table, _ in reversed(_FK_INDEXES):
        op.drop_index(ix_name, table_name=table)

    for table in _UPDATED_AT_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("updated_at")
            if table == "conduct_rule_items":
                batch.drop_column("created_at")

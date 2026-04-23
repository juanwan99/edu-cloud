"""add teacher profile fields to users

Revision ID: f7a3b2c1d456
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a3b2c1d456"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("employee_id", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("gender", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("id_card", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("title", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("hire_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("education", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("university", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("office_phone", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.String(500), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("notes")
        batch_op.drop_column("office_phone")
        batch_op.drop_column("university")
        batch_op.drop_column("education")
        batch_op.drop_column("hire_date")
        batch_op.drop_column("title")
        batch_op.drop_column("id_card")
        batch_op.drop_column("gender")
        batch_op.drop_column("employee_id")

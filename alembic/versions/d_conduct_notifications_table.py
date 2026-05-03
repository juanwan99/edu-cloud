"""add conduct_notifications table

Revision ID: d8e2f4a1b3c5
Revises: 7c3052a2ed11
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa


revision = "d8e2f4a1b3c5"
down_revision = "7c3052a2ed11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conduct_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parent_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False, index=True),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("conduct_records.id"), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("conduct_notifications")

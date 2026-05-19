"""add exam_import_sessions table

Revision ID: e1f2_import_sess
Revises: a1b2_chat_msgs
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2_import_sess"
down_revision = "a1b2_chat_msgs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exam_import_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id"), nullable=False, index=True),
        sa.Column("exam_name", sa.String(200), nullable=False),
        sa.Column("exam_type", sa.String(20), nullable=False),
        sa.Column("grade_scope", sa.String(50), nullable=False),
        sa.Column("import_mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("preview_data", sa.JSON, nullable=True),
        sa.Column("mapping_data", sa.JSON, nullable=True),
        sa.Column("result_summary", sa.JSON, nullable=True),
        sa.Column("committed_by", sa.String(36), nullable=True),
        sa.Column("exam_id", sa.String(36), sa.ForeignKey("exams.id"), nullable=True),
        sa.Column("exam_date", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("exam_import_sessions")

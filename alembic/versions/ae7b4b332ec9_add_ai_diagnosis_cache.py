"""add ai_diagnosis_cache

Revision ID: ae7b4b332ec9
Revises: ed1f8408241c
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "ae7b4b332ec9"
down_revision = "ed1f8408241c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_diagnosis_cache",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("exam_id", sa.String(64), nullable=False, index=True),
        sa.Column("school_id", sa.String(64), nullable=False),
        sa.Column("cache_key", sa.String(64), nullable=False, unique=True),
        sa.Column("scope", sa.String(16), nullable=False, server_default="class"),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("class_id", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=False, server_default="v1"),
        sa.Column("model_version", sa.String(64), nullable=False, server_default=""),
        sa.Column("result_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_diagnosis_cache")

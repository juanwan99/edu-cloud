"""add alert_threshold to conduct_class_configs + make notification record_id nullable

Revision ID: a3f7e1c2d456
Revises: 51c91f4d98e8
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a3f7e1c2d456"
down_revision = "51c91f4d98e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conduct_class_configs",
        sa.Column("alert_threshold", sa.Integer(), nullable=True),
    )
    # Make record_id nullable for alert notifications (no single triggering record)
    with op.batch_alter_table("conduct_notifications") as batch_op:
        batch_op.alter_column(
            "record_id",
            existing_type=sa.String(36),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("conduct_notifications") as batch_op:
        batch_op.alter_column(
            "record_id",
            existing_type=sa.String(36),
            nullable=False,
        )
    op.drop_column("conduct_class_configs", "alert_threshold")

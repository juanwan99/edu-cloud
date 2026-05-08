"""harden grading_result unique constraint to (school_id, answer_id)

Revision ID: b1a2c3d4e5f6
Revises: ae7b4b332ec9
Create Date: 2026-05-08
"""
from alembic import op

revision = "b1a2c3d4e5f6"
down_revision = "ae7b4b332ec9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("grading_results", recreate="always") as batch_op:
            batch_op.create_unique_constraint(
                "uq_grading_results_school_answer",
                ["school_id", "answer_id"],
            )
    else:
        op.drop_constraint("grading_results_answer_id_key", "grading_results", type_="unique")
        op.create_unique_constraint(
            "uq_grading_results_school_answer",
            "grading_results",
            ["school_id", "answer_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("grading_results", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_grading_results_school_answer", type_="unique")
            batch_op.create_unique_constraint("uq_grading_results_answer_id", ["answer_id"])
    else:
        op.drop_constraint("uq_grading_results_school_answer", "grading_results", type_="unique")
        op.create_unique_constraint(
            "grading_results_answer_id_key",
            "grading_results",
            ["answer_id"],
        )

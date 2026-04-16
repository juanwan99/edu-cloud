"""add unique constraint on questions subject_id name

Revision ID: b08103b3a6f5
Revises: 2a40f59215de
Create Date: 2026-04-12 14:07:30.454979

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b08103b3a6f5'
down_revision: Union[str, Sequence[str], None] = '2a40f59215de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("questions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_question_subject_name",
            ["subject_id", "name"],
        )


def downgrade() -> None:
    with op.batch_alter_table("questions") as batch_op:
        batch_op.drop_constraint("uq_question_subject_name", type_="unique")

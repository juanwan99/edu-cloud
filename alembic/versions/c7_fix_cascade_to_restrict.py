"""change concept_stats FK ondelete from CASCADE to RESTRICT

Revision ID: c7_fix_cascade
Revises: b1a2c3d4e5f6
Create Date: 2026-05-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7_fix_cascade'
down_revision: Union[str, Sequence[str], None] = 'b1a2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Naming convention so batch_alter_table can locate the unnamed FK
# created in 46b200fa9704 via sa.ForeignKeyConstraint without a name.
_naming_convention = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    """Change concept_stats FK ondelete from CASCADE to RESTRICT."""
    with op.batch_alter_table(
        'concept_stats',
        naming_convention=_naming_convention,
    ) as batch_op:
        batch_op.drop_constraint(
            'fk_concept_stats_concept_id_concept_graph_nodes',
            type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_concept_stats_concept_id_concept_graph_nodes',
            'concept_graph_nodes',
            ['concept_id'], ['id'],
            ondelete='RESTRICT',
        )


def downgrade() -> None:
    """Revert concept_stats FK ondelete back to CASCADE."""
    with op.batch_alter_table(
        'concept_stats',
        naming_convention=_naming_convention,
    ) as batch_op:
        batch_op.drop_constraint(
            'fk_concept_stats_concept_id_concept_graph_nodes',
            type_='foreignkey',
        )
        batch_op.create_foreign_key(
            'fk_concept_stats_concept_id_concept_graph_nodes',
            'concept_graph_nodes',
            ['concept_id'], ['id'],
            ondelete='CASCADE',
        )

"""merge_dual_heads

Revision ID: 874f6f9c14cc
Revises: 45c9d83d780e, f7a3b2c1d456
Create Date: 2026-04-22 09:28:32.547221

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '874f6f9c14cc'
down_revision: Union[str, Sequence[str], None] = ('45c9d83d780e', 'f7a3b2c1d456')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

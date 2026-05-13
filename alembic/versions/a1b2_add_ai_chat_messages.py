"""add ai_chat_messages table

Revision ID: a1b2_chat_msgs
Revises: 185f6c3280b9
Create Date: 2026-05-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2_chat_msgs'
down_revision: Union[str, Sequence[str], None] = '185f6c3280b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ai_chat_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('ai_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_in_chat', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_ai_chat_messages_session_created', 'ai_chat_messages', ['session_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_ai_chat_messages_session_created', table_name='ai_chat_messages')
    op.drop_table('ai_chat_messages')

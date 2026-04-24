"""add teacher profile fields to users

Revision ID: f7a3b2c1d456
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a3b2c1d456"
# 2026-04-24 multi-base fix: 原 down_revision=None 让 f7a3b2c1d456 与 8b3f659c1a2a
# 并列为两个 base，alembic linearization 在 fresh DB 上可能先跑此 migration，
# 但 ALTER users 依赖 8b3f659c1a2a 创建的 users 表 → sqlite3.OperationalError: no such table: users。
# 挂到 8b3f659c1a2a 下游让 linear chain 归一。8b3f659c1a2a:55-68 创建的 users 表
# 只含基础列（username/display_name/hashed_password/is_active/phone/email/last_login_at/
# id/created_at/updated_at），与 f7a3b2c1d456 新增的 9 列（employee_id/gender/id_card/
# title/hire_date/education/university/office_phone/notes）完全不重叠。
# 生产 edu_cloud.db 已 stamp 到 e241e1568792 或之后，不会重跑此 body。
# refs: docs/plans/2026-04-13-migration-gate-repair-design.md (同类历史 migration fix)
down_revision = "8b3f659c1a2a"
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

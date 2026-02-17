"""add audit log actor cache

Revision ID: 8b1d7c2e4f9a
Revises: 3a9c1d0b6f44
Create Date: 2026-02-16 21:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8b1d7c2e4f9a"
down_revision = "3a9c1d0b6f44"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("audit_logs", sa.Column("actor_name_cached", sa.String(length=120), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_username_cached", sa.String(length=80), nullable=True))


def downgrade():
    op.drop_column("audit_logs", "actor_username_cached")
    op.drop_column("audit_logs", "actor_name_cached")

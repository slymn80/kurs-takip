"""add student is_active

Revision ID: 7d2c0a8d1e3b
Revises: 5f4d2c1a6b2b
Create Date: 2026-02-16 20:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7d2c0a8d1e3b"
down_revision = "5f4d2c1a6b2b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("students", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("students", "is_active", server_default=None)


def downgrade():
    op.drop_column("students", "is_active")

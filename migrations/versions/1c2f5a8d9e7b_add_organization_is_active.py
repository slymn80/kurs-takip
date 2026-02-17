"""add organization is_active

Revision ID: 1c2f5a8d9e7b
Revises: 8b1d7c2e4f9a
Create Date: 2026-02-16 22:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1c2f5a8d9e7b"
down_revision = "8b1d7c2e4f9a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("organizations", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("organizations", "is_active", server_default=None)


def downgrade():
    op.drop_column("organizations", "is_active")

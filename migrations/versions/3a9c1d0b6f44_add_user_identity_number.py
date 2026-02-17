"""add user identity number

Revision ID: 3a9c1d0b6f44
Revises: 7d2c0a8d1e3b
Create Date: 2026-02-16 21:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3a9c1d0b6f44"
down_revision = "7d2c0a8d1e3b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("identity_number", sa.String(length=20), nullable=True))
    op.create_unique_constraint("uq_users_identity_number", "users", ["identity_number"])


def downgrade():
    op.drop_constraint("uq_users_identity_number", "users", type_="unique")
    op.drop_column("users", "identity_number")

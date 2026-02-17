"""add location and course_type is_active

Revision ID: 4b7c9d1e2f6a
Revises: 1c2f5a8d9e7b
Create Date: 2026-02-16 22:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4b7c9d1e2f6a"
down_revision = "1c2f5a8d9e7b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("locations", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("course_types", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("locations", "is_active", server_default=None)
    op.alter_column("course_types", "is_active", server_default=None)


def downgrade():
    op.drop_column("course_types", "is_active")
    op.drop_column("locations", "is_active")

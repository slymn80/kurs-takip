"""add teacher identity number

Revision ID: 0d3b7a3e7c12
Revises: 9b1c2f0a1f7a
Create Date: 2026-02-16 19:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0d3b7a3e7c12"
down_revision = "9b1c2f0a1f7a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("teachers", sa.Column("identity_number", sa.String(length=20), nullable=True))
    op.create_unique_constraint("uq_teachers_identity_number", "teachers", ["identity_number"])


def downgrade():
    op.drop_constraint("uq_teachers_identity_number", "teachers", type_="unique")
    op.drop_column("teachers", "identity_number")

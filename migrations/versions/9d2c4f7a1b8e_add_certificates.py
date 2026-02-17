"""add certificates

Revision ID: 9d2c4f7a1b8e
Revises: 2a7f3c9e1b6d
Create Date: 2026-02-17 01:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d2c4f7a1b8e"
down_revision = "2a7f3c9e1b6d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "certificates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id"), nullable=False),
        sa.Column("serial_no", sa.String(length=40), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=True),
        sa.Column("issued_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_unique_constraint("uq_certificates_enrollment", "certificates", ["enrollment_id"])
    op.create_unique_constraint("uq_certificates_serial", "certificates", ["serial_no"])


def downgrade():
    op.drop_table("certificates")

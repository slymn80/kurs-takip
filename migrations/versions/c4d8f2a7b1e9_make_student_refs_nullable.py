"""make student refs nullable

Revision ID: c4d8f2a7b1e9
Revises: b3f2c9a1e7ab
Create Date: 2026-02-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4d8f2a7b1e9"
down_revision = "b3f2c9a1e7ab"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("enrollments", "student_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("attendance", "student_id", existing_type=sa.Integer(), nullable=True)


def downgrade():
    op.alter_column("attendance", "student_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("enrollments", "student_id", existing_type=sa.Integer(), nullable=False)

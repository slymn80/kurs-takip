"""add course teacher name cached

Revision ID: 5f4d2c1a6b2b
Revises: 0d3b7a3e7c12
Create Date: 2026-02-16 19:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5f4d2c1a6b2b"
down_revision = "0d3b7a3e7c12"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("courses", sa.Column("teacher_name_cached", sa.String(length=120), nullable=True))
    op.execute(
        """
        UPDATE courses
        SET teacher_name_cached = teachers.full_name
        FROM teachers
        WHERE courses.teacher_id = teachers.id
        """
    )


def downgrade():
    op.drop_column("courses", "teacher_name_cached")

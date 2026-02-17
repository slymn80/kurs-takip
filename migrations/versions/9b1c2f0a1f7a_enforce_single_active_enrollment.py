"""enforce single active enrollment per student

Revision ID: 9b1c2f0a1f7a
Revises: 9218fee7a146
Create Date: 2026-02-16 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9b1c2f0a1f7a"
down_revision = "9218fee7a146"
branch_labels = None
depends_on = None


def upgrade():
    # Keep only the most recent active enrollment per student
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY enrolled_at DESC, id DESC) AS rn
            FROM enrollments
            WHERE status = 'active'
        )
        UPDATE enrollments
        SET status = 'inactive'
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )
    op.create_index(
        "uq_enrollments_student_active",
        "enrollments",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'")
    )


def downgrade():
    op.drop_index("uq_enrollments_student_active", table_name="enrollments")

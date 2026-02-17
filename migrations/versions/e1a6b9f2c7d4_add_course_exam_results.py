"""add course exam results

Revision ID: e1a6b9f2c7d4
Revises: d4b7c2a1f0b3
Create Date: 2026-02-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1a6b9f2c7d4"
down_revision = "d4b7c2a1f0b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "course_exam_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id"), nullable=False, unique=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(), nullable=True),
        sa.Column("evaluated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"))
    )
    op.create_index(
        "ix_course_exam_results_enrollment",
        "course_exam_results",
        ["enrollment_id"]
    )


def downgrade():
    op.drop_index("ix_course_exam_results_enrollment", table_name="course_exam_results")
    op.drop_table("course_exam_results")

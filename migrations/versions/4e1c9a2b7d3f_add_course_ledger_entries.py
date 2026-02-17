"""add course ledger entries

Revision ID: 4e1c9a2b7d3f
Revises: 9d2c4f7a1b8e
Create Date: 2026-02-17 01:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4e1c9a2b7d3f"
down_revision = "9d2c4f7a1b8e"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "course_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("academic_year", sa.String(length=9), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=True),
        sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("course_title_cached", sa.String(length=200), nullable=False),
        sa.Column("organization_name_cached", sa.String(length=120)),
        sa.Column("location_name_cached", sa.String(length=120)),
        sa.Column("course_type_name_cached", sa.String(length=120)),
        sa.Column("teacher_name_cached", sa.String(length=120)),
        sa.Column("student_full_name_cached", sa.String(length=120), nullable=False),
        sa.Column("student_iin_cached", sa.String(length=20), nullable=False),
        sa.Column("course_start_date", sa.Date()),
        sa.Column("course_end_date", sa.Date()),
        sa.Column("attendance_percent", sa.Float(), nullable=True),
        sa.Column("result", sa.String(length=40)),
        sa.Column("score", sa.Integer()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime())
    )
    op.create_unique_constraint("uq_course_ledger_entry", "course_ledger_entries", ["academic_year", "course_id", "student_id"])
    op.create_index("ix_course_ledger_course_year", "course_ledger_entries", ["course_id", "academic_year"])


def downgrade():
    op.drop_index("ix_course_ledger_course_year", table_name="course_ledger_entries")
    op.drop_table("course_ledger_entries")

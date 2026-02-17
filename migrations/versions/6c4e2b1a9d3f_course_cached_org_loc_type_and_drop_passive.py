"""course cached org/loc/type and drop passive flags

Revision ID: 6c4e2b1a9d3f
Revises: 4b7c9d1e2f6a
Create Date: 2026-02-16 23:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6c4e2b1a9d3f"
down_revision = "4b7c9d1e2f6a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("courses", sa.Column("organization_name_cached", sa.String(length=120), nullable=True))
    op.add_column("courses", sa.Column("course_type_name_cached", sa.String(length=120), nullable=True))
    op.add_column("courses", sa.Column("location_name_cached", sa.String(length=120), nullable=True))

    op.execute(
        """
        UPDATE courses
        SET organization_name_cached = organizations.name
        FROM organizations
        WHERE courses.organization_id = organizations.id
        """
    )
    op.execute(
        """
        UPDATE courses
        SET course_type_name_cached = course_types.name
        FROM course_types
        WHERE courses.course_type_id = course_types.id
        """
    )
    op.execute(
        """
        UPDATE courses
        SET location_name_cached = locations.name
        FROM locations
        WHERE courses.location_id = locations.id
        """
    )

    op.alter_column("courses", "organization_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("courses", "course_type_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("courses", "location_id", existing_type=sa.Integer(), nullable=True)

    op.drop_column("organizations", "is_active")
    op.drop_column("locations", "is_active")
    op.drop_column("course_types", "is_active")


def downgrade():
    op.add_column("course_types", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("locations", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("organizations", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.alter_column("courses", "location_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("courses", "course_type_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("courses", "organization_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("courses", "location_name_cached")
    op.drop_column("courses", "course_type_name_cached")
    op.drop_column("courses", "organization_name_cached")

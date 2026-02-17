"""add placement question group

Revision ID: b3f2c9a1e7ab
Revises: d3a6f9b1c7e2
Create Date: 2026-02-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b3f2c9a1e7ab"
down_revision = "d3a6f9b1c7e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("placement_questions", sa.Column("group_name", sa.String(length=60), nullable=True))
    op.execute("UPDATE placement_questions SET group_name = 'Grup 1' WHERE group_name IS NULL")
    op.execute("UPDATE placement_questions SET is_active = TRUE, is_approved = TRUE")
    op.alter_column("placement_questions", "group_name", nullable=False)
    op.create_index("ix_placement_questions_group_name", "placement_questions", ["group_name"])


def downgrade():
    op.drop_index("ix_placement_questions_group_name", table_name="placement_questions")
    op.drop_column("placement_questions", "group_name")

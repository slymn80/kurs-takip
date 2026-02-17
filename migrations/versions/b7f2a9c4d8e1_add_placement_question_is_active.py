"""add_placement_question_is_active

Revision ID: b7f2a9c4d8e1
Revises: 4e1c9a2b7d3f
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7f2a9c4d8e1"
down_revision = "4e1c9a2b7d3f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "placement_questions",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"))
    )


def downgrade():
    op.drop_column("placement_questions", "is_active")

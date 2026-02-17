"""add_placement_question_approval_fields

Revision ID: d3a6f9b1c7e2
Revises: c2f5a1d8e4b3
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d3a6f9b1c7e2"
down_revision = "c2f5a1d8e4b3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "placement_questions",
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("false"))
    )
    op.add_column("placement_questions", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("placement_questions", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_placement_questions_reviewed_by_user_id",
        "placement_questions",
        "users",
        ["reviewed_by_user_id"],
        ["id"]
    )


def downgrade():
    op.drop_constraint("fk_placement_questions_reviewed_by_user_id", "placement_questions", type_="foreignkey")
    op.drop_column("placement_questions", "reviewed_by_user_id")
    op.drop_column("placement_questions", "reviewed_at")
    op.drop_column("placement_questions", "is_approved")

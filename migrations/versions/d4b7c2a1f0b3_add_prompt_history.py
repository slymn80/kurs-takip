"""add placement prompt history

Revision ID: d4b7c2a1f0b3
Revises: c4d8f2a7b1e9
Create Date: 2026-02-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4b7c2a1f0b3"
down_revision = "c4d8f2a7b1e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "placement_prompt_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"))
    )
    op.create_index(
        "ix_prompt_history_created_at",
        "placement_prompt_history",
        ["created_at"]
    )


def downgrade():
    op.drop_index("ix_prompt_history_created_at", table_name="placement_prompt_history")
    op.drop_table("placement_prompt_history")

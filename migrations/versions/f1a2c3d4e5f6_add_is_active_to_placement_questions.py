"""add is_active to placement_questions

Revision ID: f1a2c3d4e5f6
Revises: e1a6b9f2c7d4
Create Date: 2026-02-17
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a2c3d4e5f6"
down_revision = "e1a6b9f2c7d4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    exists = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='placement_questions' AND column_name='is_active'"
    )).first()
    if not exists:
        op.add_column(
            "placement_questions",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"))
        )
        op.alter_column("placement_questions", "is_active", server_default=None)


def downgrade():
    bind = op.get_bind()
    exists = bind.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='placement_questions' AND column_name='is_active'"
    )).first()
    if exists:
        op.drop_column("placement_questions", "is_active")

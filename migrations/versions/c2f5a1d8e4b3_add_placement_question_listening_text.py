"""add_placement_question_listening_text

Revision ID: c2f5a1d8e4b3
Revises: b7f2a9c4d8e1
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c2f5a1d8e4b3"
down_revision = "b7f2a9c4d8e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("placement_questions", sa.Column("listening_text", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("placement_questions", "listening_text")

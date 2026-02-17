"""add listening audio url to placement questions

Revision ID: 2a7f3c9e1b6d
Revises: 0f1a2c3d4b5e
Create Date: 2026-02-17 00:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2a7f3c9e1b6d"
down_revision = "0f1a2c3d4b5e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("placement_questions", sa.Column("audio_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("placement_questions", "audio_url")

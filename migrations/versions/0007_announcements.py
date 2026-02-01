"""add announcements

Revision ID: 0007_announcements
Revises: 0006_messages
Create Date: 2026-02-01 05:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007_announcements'
down_revision = '0006_messages'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'announcements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.String(length=300), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )


def downgrade():
    op.drop_table('announcements')

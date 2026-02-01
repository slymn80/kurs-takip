"""add messages

Revision ID: 0006_messages
Revises: 0005_course_type_delivery_mode
Create Date: 2026-02-01 05:03:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_messages'
down_revision = '0005_course_type_delivery_mode'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )


def downgrade():
    op.drop_table('messages')

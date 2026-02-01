"""add course term

Revision ID: 0008_course_term
Revises: 0007_announcements
Create Date: 2026-02-01 13:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008_course_term'
down_revision = '0007_announcements'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('courses') as batch_op:
        batch_op.add_column(sa.Column('term', sa.String(length=10), nullable=False, server_default='fall'))


def downgrade():
    with op.batch_alter_table('courses') as batch_op:
        batch_op.drop_column('term')

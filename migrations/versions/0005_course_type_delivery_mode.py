"""add course type delivery mode

Revision ID: 0005_course_type_delivery_mode
Revises: 0004_course_type_hours
Create Date: 2026-02-01 04:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_course_type_delivery_mode'
down_revision = '0004_course_type_hours'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('course_types') as batch_op:
        batch_op.add_column(sa.Column('delivery_mode', sa.String(length=20), nullable=False, server_default='in_person'))


def downgrade():
    with op.batch_alter_table('course_types') as batch_op:
        batch_op.drop_column('delivery_mode')

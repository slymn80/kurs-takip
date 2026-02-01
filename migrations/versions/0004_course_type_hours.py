"""add course type hours

Revision ID: 0004_course_type_hours
Revises: 0003_student_fields
Create Date: 2026-02-01 03:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_course_type_hours'
down_revision = '0003_student_fields'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('course_types') as batch_op:
        batch_op.add_column(sa.Column('course_hours', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('course_types') as batch_op:
        batch_op.drop_column('course_hours')

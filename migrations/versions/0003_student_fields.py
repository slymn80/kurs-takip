"""add student iin education

Revision ID: 0003_student_fields
Revises: 0002_master_fields
Create Date: 2026-02-01 03:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_student_fields'
down_revision = '0002_master_fields'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students') as batch_op:
        batch_op.add_column(sa.Column('iin', sa.String(length=20), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('education_level', sa.String(length=40), nullable=False, server_default='other'))


def downgrade():
    with op.batch_alter_table('students') as batch_op:
        batch_op.drop_column('education_level')
        batch_op.drop_column('iin')

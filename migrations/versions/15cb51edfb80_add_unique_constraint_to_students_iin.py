"""add unique constraint to students iin

Revision ID: 15cb51edfb80
Revises: ccf53edfcc24
Create Date: 2026-02-18 14:00:10.287466

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '15cb51edfb80'
down_revision = 'ccf53edfcc24'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint('uq_students_iin', 'students', ['iin'])


def downgrade():
    op.drop_constraint('uq_students_iin', 'students', type_='unique')

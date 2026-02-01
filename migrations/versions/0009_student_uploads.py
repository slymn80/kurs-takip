"""add student upload fields

Revision ID: 0009_student_uploads
Revises: 0008_course_term
Create Date: 2026-02-01 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009_student_uploads'
down_revision = '0008_course_term'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students') as batch_op:
        batch_op.add_column(sa.Column('photo_path', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('id_image_path', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('students') as batch_op:
        batch_op.drop_column('id_image_path')
        batch_op.drop_column('photo_path')

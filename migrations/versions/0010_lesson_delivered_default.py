"""set session lesson_delivered default false

Revision ID: 0010_lesson_delivered_default
Revises: 0009_student_uploads
Create Date: 2026-02-01 21:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0010_lesson_delivered_default'
down_revision = '0009_student_uploads'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE sessions SET lesson_delivered = FALSE")
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.alter_column('lesson_delivered', server_default=sa.false())


def downgrade():
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.alter_column('lesson_delivered', server_default=sa.true())

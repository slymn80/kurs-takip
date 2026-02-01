"""add master fields

Revision ID: 0002_master_fields
Revises: 0001_initial
Create Date: 2026-02-01 02:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_master_fields'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('organizations') as batch_op:
        batch_op.add_column(sa.Column('responsible_person', sa.String(length=120), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('phone', sa.String(length=30), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=False, server_default=''))

    with op.batch_alter_table('locations') as batch_op:
        batch_op.add_column(sa.Column('has_smart_board', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    with op.batch_alter_table('teachers') as batch_op:
        batch_op.add_column(sa.Column('full_name', sa.String(length=120), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('branch', sa.String(length=40), nullable=False, server_default='other'))
        batch_op.add_column(sa.Column('phone', sa.String(length=30), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('email', sa.String(length=120), nullable=False, server_default=''))
        batch_op.alter_column('title', existing_type=sa.String(length=80), nullable=False, server_default='teacher')
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table('courses') as batch_op:
        batch_op.add_column(sa.Column('teacher_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_courses_teacher_id', 'teachers', ['teacher_id'], ['id'])
        batch_op.alter_column('teacher_user_id', existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table('sessions') as batch_op:
        batch_op.add_column(sa.Column('lesson_delivered', sa.Boolean(), nullable=False, server_default=sa.text('1')))


def downgrade():
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.drop_column('lesson_delivered')

    with op.batch_alter_table('courses') as batch_op:
        batch_op.drop_constraint('fk_courses_teacher_id', type_='foreignkey')
        batch_op.drop_column('teacher_id')
        batch_op.alter_column('teacher_user_id', existing_type=sa.Integer(), nullable=False)

    with op.batch_alter_table('teachers') as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('email')
        batch_op.drop_column('phone')
        batch_op.drop_column('branch')
        batch_op.drop_column('full_name')
        batch_op.alter_column('title', existing_type=sa.String(length=20), nullable=True)

    with op.batch_alter_table('locations') as batch_op:
        batch_op.drop_column('has_smart_board')

    with op.batch_alter_table('organizations') as batch_op:
        batch_op.drop_column('email')
        batch_op.drop_column('phone')
        batch_op.drop_column('responsible_person')

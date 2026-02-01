"""initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-01 01:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=30)),
        sa.Column('email', sa.String(length=120)),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('password_hash', sa.String(length=200), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), default=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime())
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('address', sa.String(length=200)),
        sa.Column('notes', sa.Text())
    )
    op.create_table(
        'locations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('address', sa.String(length=200)),
        sa.Column('capacity', sa.Integer()),
        sa.Column('notes', sa.Text())
    )
    op.create_table(
        'course_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text())
    )
    op.create_table(
        'teachers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(length=80)),
        sa.Column('notes', sa.Text())
    )
    op.create_table(
        'students',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=30)),
        sa.Column('email', sa.String(length=120)),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime())
    )
    op.create_table(
        'courses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('course_type_id', sa.Integer(), sa.ForeignKey('course_types.id'), nullable=False),
        sa.Column('location_id', sa.Integer(), sa.ForeignKey('locations.id'), nullable=False),
        sa.Column('teacher_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('schedule_json', sa.JSON(), nullable=True),
        sa.Column('capacity', sa.Integer()),
        sa.Column('status', sa.String(length=20)),
        sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime())
    )
    op.create_index('ix_courses_teacher_status', 'courses', ['teacher_user_id', 'status'])

    op.create_table(
        'enrollments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('enrolled_at', sa.DateTime()),
        sa.Column('status', sa.String(length=20))
    )
    op.create_unique_constraint('uq_enrollments_course_student', 'enrollments', ['course_id', 'student_id'])

    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_id', sa.Integer(), sa.ForeignKey('courses.id'), nullable=False),
        sa.Column('session_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time()),
        sa.Column('end_time', sa.Time()),
        sa.Column('topic', sa.String(length=200)),
        sa.Column('created_at', sa.DateTime())
    )
    op.create_index('ix_sessions_course_date', 'sessions', ['course_id', 'session_date'])

    op.create_table(
        'attendance',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('sessions.id'), nullable=False),
        sa.Column('student_id', sa.Integer(), sa.ForeignKey('students.id'), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('note', sa.Text()),
        sa.Column('marked_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('marked_at', sa.DateTime())
    )
    op.create_unique_constraint('uq_attendance_session_student', 'attendance', ['session_id', 'student_id'])

    op.create_table(
        'system_settings',
        sa.Column('key', sa.String(length=80), primary_key=True),
        sa.Column('value', sa.Text())
    )
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('action', sa.String(length=80), nullable=False),
        sa.Column('entity_type', sa.String(length=80), nullable=False),
        sa.Column('entity_id', sa.Integer()),
        sa.Column('before_json', sa.Text()),
        sa.Column('after_json', sa.Text()),
        sa.Column('created_at', sa.DateTime())
    )
    op.create_table(
        'events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20)),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('last_error', sa.Text())
    )


def downgrade():
    op.drop_table('events')
    op.drop_table('audit_logs')
    op.drop_table('system_settings')
    op.drop_table('attendance')
    op.drop_table('sessions')
    op.drop_table('enrollments')
    op.drop_index('ix_courses_teacher_status', table_name='courses')
    op.drop_table('courses')
    op.drop_table('students')
    op.drop_table('teachers')
    op.drop_table('course_types')
    op.drop_table('locations')
    op.drop_table('organizations')
    op.drop_index('ix_users_username', table_name='users')
    op.drop_table('users')

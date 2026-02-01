from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint, Index
from .extensions import db


def now_utc():
    return datetime.utcnow()


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    role = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    must_change_password = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_utc)


class Organization(db.Model):
    __tablename__ = "organizations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    responsible_person = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200))
    notes = db.Column(db.Text)


class Location(db.Model):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200))
    capacity = db.Column(db.Integer)
    has_smart_board = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text)


class CourseType(db.Model):
    __tablename__ = "course_types"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    course_hours = db.Column(db.Integer, nullable=False)
    delivery_mode = db.Column(db.String(20), nullable=False, default="in_person")
    description = db.Column(db.Text)


class Teacher(db.Model):
    __tablename__ = "teachers"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    full_name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(20), nullable=False)
    branch = db.Column(db.String(40), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    notes = db.Column(db.Text)
    user = db.relationship("User")


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    iin = db.Column(db.String(20), nullable=False)
    education_level = db.Column(db.String(40), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    photo_path = db.Column(db.String(255))
    id_image_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now_utc)


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    course_type_id = db.Column(db.Integer, db.ForeignKey("course_types.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True)
    teacher_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    schedule_json = db.Column(db.JSON)
    term = db.Column(db.String(10), nullable=False, default="fall")
    capacity = db.Column(db.Integer)
    status = db.Column(db.String(20), default="active")
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc)

    organization = db.relationship("Organization")
    course_type = db.relationship("CourseType")
    location = db.relationship("Location")
    teacher = db.relationship("Teacher")

    __table_args__ = (
        Index("ix_courses_teacher_status", "teacher_user_id", "status"),
    )


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=now_utc)
    status = db.Column(db.String(20), default="active")

    student = db.relationship("Student")
    course = db.relationship("Course")

    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_enrollments_course_student"),
    )


class Session(db.Model):
    __tablename__ = "sessions"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    topic = db.Column(db.String(200))
    lesson_delivered = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=now_utc)

    course = db.relationship("Course")

    __table_args__ = (
        Index("ix_sessions_course_date", "course_id", "session_date"),
    )


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("sessions.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    note = db.Column(db.Text)
    marked_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    marked_at = db.Column(db.DateTime, default=now_utc)

    student = db.relationship("Student")
    session = db.relationship("Session")

    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),
    )


class SystemSetting(db.Model):
    __tablename__ = "system_settings"
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(80), nullable=False)
    entity_id = db.Column(db.Integer)
    before_json = db.Column(db.Text)
    after_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now_utc)


class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(80), nullable=False)
    payload_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=now_utc)
    last_error = db.Column(db.Text)


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc)

    user = db.relationship("User")


class Announcement(db.Model):
    __tablename__ = "announcements"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    content = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=now_utc)

    user = db.relationship("User")

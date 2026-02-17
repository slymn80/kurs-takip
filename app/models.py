from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint, Index, text
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
    identity_number = db.Column(db.String(20), unique=True)
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
    identity_number = db.Column(db.String(20), unique=True)
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
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_utc)


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    course_type_id = db.Column(db.Integer, db.ForeignKey("course_types.id"), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True)
    teacher_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    teacher_name_cached = db.Column(db.String(120))
    organization_name_cached = db.Column(db.String(120))
    course_type_name_cached = db.Column(db.String(120))
    location_name_cached = db.Column(db.String(120))
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
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
    enrolled_at = db.Column(db.DateTime, default=now_utc)
    status = db.Column(db.String(20), default="active")

    student = db.relationship("Student")
    course = db.relationship("Course")

    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uq_enrollments_course_student"),
        Index(
            "uq_enrollments_student_active",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'active'")
        ),
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
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
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
    actor_name_cached = db.Column(db.String(120))
    actor_username_cached = db.Column(db.String(80))
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


class PreRegistration(db.Model):
    __tablename__ = "pre_registrations"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"))
    full_name = db.Column(db.String(120), nullable=False)
    iin = db.Column(db.String(20), nullable=False)
    education_level = db.Column(db.String(40), nullable=False)
    course_level = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    photo_path = db.Column(db.String(255))
    id_image_path = db.Column(db.String(255))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=now_utc)

    student = db.relationship("Student")

    __table_args__ = (
        Index("ix_pre_regs_iin_status", "iin", "status"),
    )


class PlacementCandidate(db.Model):
    __tablename__ = "placement_candidates"
    id = db.Column(db.Integer, primary_key=True)
    iin = db.Column(db.String(20), nullable=False, unique=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=now_utc)


class PlacementQuestion(db.Model):
    __tablename__ = "placement_questions"
    id = db.Column(db.Integer, primary_key=True)
    skill = db.Column(db.String(20), nullable=False)
    difficulty = db.Column(db.String(10), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    group_name = db.Column(db.String(60), nullable=False, default="Grup 1")
    audio_url = db.Column(db.Text)
    listening_text = db.Column(db.Text)
    options_json = db.Column(db.Text, nullable=False)
    correct_index = db.Column(db.Integer, nullable=False)
    explanation = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_approved = db.Column(db.Boolean, default=False)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=now_utc)

    reviewed_by = db.relationship("User")

class PlacementTest(db.Model):
    __tablename__ = "placement_tests"
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("placement_candidates.id"), nullable=False)
    started_at = db.Column(db.DateTime, default=now_utc)
    completed_at = db.Column(db.DateTime)
    total_questions = db.Column(db.Integer, default=30)
    correct_count = db.Column(db.Integer, default=0)
    score_percent = db.Column(db.Float, default=0)
    level = db.Column(db.String(10))
    model_used = db.Column(db.String(40))
    mode = db.Column(db.String(20), default="pool")

    candidate = db.relationship("PlacementCandidate")


class PlacementTestQuestion(db.Model):
    __tablename__ = "placement_test_questions"
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("placement_tests.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("placement_questions.id"), nullable=False)
    question_order = db.Column(db.Integer, nullable=False)

    test = db.relationship("PlacementTest")
    question = db.relationship("PlacementQuestion")


class PlacementAnswer(db.Model):
    __tablename__ = "placement_answers"
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("placement_tests.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("placement_questions.id"), nullable=False)
    selected_index = db.Column(db.Integer)
    is_correct = db.Column(db.Boolean, default=False)

    test = db.relationship("PlacementTest")
    question = db.relationship("PlacementQuestion")


class Certificate(db.Model):
    __tablename__ = "certificates"
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"), nullable=False, unique=True)
    serial_no = db.Column(db.String(40), unique=True, nullable=False)
    issued_at = db.Column(db.DateTime, default=now_utc)
    issued_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    enrollment = db.relationship("Enrollment")
    issued_by = db.relationship("User")


class CourseLedgerEntry(db.Model):
    __tablename__ = "course_ledger_entries"
    id = db.Column(db.Integer, primary_key=True)
    academic_year = db.Column(db.String(9), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=True)
    teacher_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    course_title_cached = db.Column(db.String(200), nullable=False)
    organization_name_cached = db.Column(db.String(120))
    location_name_cached = db.Column(db.String(120))
    course_type_name_cached = db.Column(db.String(120))
    teacher_name_cached = db.Column(db.String(120))
    student_full_name_cached = db.Column(db.String(120), nullable=False)
    student_iin_cached = db.Column(db.String(20), nullable=False)
    course_start_date = db.Column(db.Date)
    course_end_date = db.Column(db.Date)
    attendance_percent = db.Column(db.Float, default=0)
    result = db.Column(db.String(40), default="Tamamladı")
    score = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now_utc)
    updated_at = db.Column(db.DateTime, default=now_utc, onupdate=now_utc)

    course = db.relationship("Course")
    student = db.relationship("Student")
    teacher_user = db.relationship("User")

    __table_args__ = (
        UniqueConstraint("academic_year", "course_id", "student_id", name="uq_course_ledger_entry"),
        Index("ix_course_ledger_course_year", "course_id", "academic_year"),
    )
class ApiToken(db.Model):
    __tablename__ = "api_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False, default="default")
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=now_utc)
    last_used_at = db.Column(db.DateTime)

    user = db.relationship("User")

    __table_args__ = (
        Index("ix_api_tokens_user_active", "user_id", "is_active"),
    )

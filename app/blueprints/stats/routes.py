from datetime import date
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from sqlalchemy import func
from ...extensions import db
from ...models import Course, CourseType, Organization, Attendance, Session, Teacher, Enrollment
from ...security import require_roles


stats_bp = Blueprint("stats", __name__)


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@stats_bp.route("/")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def index():
    date_from = _parse_date(request.args.get("date_from"))
    date_to = _parse_date(request.args.get("date_to"))
    organization_id = request.args.get("organization_id", type=int)
    course_type_id = request.args.get("course_type_id", type=int)
    teacher_id = request.args.get("teacher_id", type=int)

    course_filters = []
    if organization_id:
        course_filters.append(Course.organization_id == organization_id)
    if course_type_id:
        course_filters.append(Course.course_type_id == course_type_id)
    if current_user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        if teacher:
            teacher_id = teacher.id
            course_filters.append(Course.teacher_id == teacher.id)
        else:
            course_filters.append(Course.teacher_user_id == current_user.id)
    elif teacher_id:
        course_filters.append(Course.teacher_id == teacher_id)

    session_filters = []
    if date_from:
        session_filters.append(Session.session_date >= date_from)
    if date_to:
        session_filters.append(Session.session_date <= date_to)
    session_filters.append(Session.lesson_delivered == True)

    base_courses = Course.query.filter(*course_filters)

    active_courses = base_courses.filter(Course.status == "active").count()
    ended_courses = base_courses.filter(Course.status != "active").count()

    total_students = db.session.query(func.count(func.distinct(Enrollment.student_id))).join(Course, Enrollment.course_id == Course.id).filter(*course_filters).scalar() or 0

    total_sessions = db.session.query(func.count(Session.id)).join(Course).filter(*course_filters, *session_filters).scalar() or 0
    total_attendance = db.session.query(func.count(Attendance.id)).join(Session).join(Course).filter(*course_filters, *session_filters).scalar() or 0
    absent_attendance = db.session.query(func.count(Attendance.id)).join(Session).join(Course).filter(*course_filters, *session_filters, Attendance.status == "absent").scalar() or 0
    absence_rate = round((absent_attendance / total_attendance) * 100, 2) if total_attendance else 0

    org_counts = db.session.query(Organization.name, func.count(Course.id)).join(Course).filter(*course_filters).group_by(Organization.name).all()
    type_counts = db.session.query(CourseType.name, func.count(Course.id)).join(Course).filter(*course_filters).group_by(CourseType.name).all()
    teacher_counts = db.session.query(Teacher.full_name, func.count(Course.id)).join(Course, Course.teacher_id == Teacher.id).filter(*course_filters).group_by(Teacher.full_name).all()

    if db.engine.dialect.name == "sqlite":
        month_expr = func.strftime('%Y-%m', Session.session_date)
    else:
        month_expr = func.date_trunc('month', Session.session_date)

    monthly_absent = db.session.query(
        month_expr,
        func.count(Attendance.id)
    ).join(Attendance).join(Course).filter(
        *course_filters,
        *session_filters,
        Attendance.status == "absent"
    ).group_by(month_expr).order_by(month_expr).all()

    attendance_by_course_type = db.session.query(
        CourseType.name,
        func.count(Attendance.id)
    ).join(Course, Course.course_type_id == CourseType.id).join(Session, Session.course_id == Course.id).join(Attendance, Attendance.session_id == Session.id)
    attendance_by_course_type = attendance_by_course_type.filter(*course_filters, *session_filters).group_by(CourseType.name).all()

    organizations = Organization.query.order_by(Organization.name).all()
    course_types = CourseType.query.order_by(CourseType.name).all()
    if current_user.role == "teacher":
        teachers = Teacher.query.filter_by(user_id=current_user.id).all()
    else:
        teachers = Teacher.query.order_by(Teacher.full_name).all()

    return render_template(
        "stats/index.html",
        org_counts=org_counts,
        type_counts=type_counts,
        teacher_counts=teacher_counts,
        monthly_absent=monthly_absent,
        attendance_by_course_type=attendance_by_course_type,
        active_courses=active_courses,
        ended_courses=ended_courses,
        total_students=total_students,
        total_sessions=total_sessions,
        absence_rate=absence_rate,
        organizations=organizations,
        course_types=course_types,
        teachers=teachers,
        filters={
            "date_from": request.args.get("date_from", ""),
            "date_to": request.args.get("date_to", ""),
            "organization_id": organization_id or "",
            "course_type_id": course_type_id or "",
            "teacher_id": teacher_id or ""
        }
    )

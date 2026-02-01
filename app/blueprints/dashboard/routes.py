from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from ...extensions import db
from ...models import Course, Student, Session, Attendance, Enrollment, Teacher, User


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
@login_required
def index():
    today = date.today()
    course_query = Course.query
    if current_user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        if teacher:
            course_query = course_query.filter(Course.teacher_id == teacher.id)
        else:
            course_query = course_query.filter_by(teacher_user_id=current_user.id)

    active_courses = course_query.filter(Course.status == "active").count()
    total_students = Student.query.count()

    today_sessions = Session.query.join(Course).filter(Session.session_date == today)
    if current_user.role == "teacher":
        if teacher:
            today_sessions = today_sessions.filter(Course.teacher_id == teacher.id)
        else:
            today_sessions = today_sessions.filter(Course.teacher_user_id == current_user.id)
    today_sessions_count = today_sessions.count()

    month_start = date(today.year, today.month, 1)
    total_attendance = Attendance.query.join(Session).filter(Session.session_date >= month_start, Session.lesson_delivered == True).count()
    absent_attendance = Attendance.query.join(Session).filter(Session.session_date >= month_start, Session.lesson_delivered == True, Attendance.status == "absent").count()
    absence_rate = round((absent_attendance / total_attendance) * 100, 2) if total_attendance else 0

    if current_user.role == "teacher":
        active_teachers = 1
    else:
        active_teachers = db.session.query(Teacher).outerjoin(User, Teacher.user_id == User.id).filter(
            (Teacher.user_id == None) | (User.is_active == True)
        ).count()

    recent_enrollments = Enrollment.query.order_by(Enrollment.enrolled_at.desc()).limit(6).all()

    return render_template(
        "dashboard.html",
        active_courses=active_courses,
        total_students=total_students,
        today_sessions_count=today_sessions_count,
        absence_rate=absence_rate,
        active_teachers=active_teachers,
        recent_enrollments=recent_enrollments
    )

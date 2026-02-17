from datetime import date
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
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
        teacher_course_ids = [c.id for c in course_query.with_entities(Course.id).all()]
    else:
        teacher_course_ids = None

    active_courses = course_query.filter(Course.status == "active").count()
    base_students_query = db.session.query(Enrollment.student_id).join(Course, Enrollment.course_id == Course.id).join(
        Student, Enrollment.student_id == Student.id
    ).filter(
        Enrollment.status == "active",
        Course.status == "active",
        Student.is_active == True
    )
    if current_user.role == "teacher":
        total_students = base_students_query.filter(
            Course.id.in_(teacher_course_ids)
        ).distinct().count()
    else:
        total_students = base_students_query.distinct().count()

    today_sessions = Session.query.join(Course).filter(Session.session_date == today)
    if current_user.role == "teacher":
        if teacher:
            today_sessions = today_sessions.filter(Course.teacher_id == teacher.id)
        else:
            today_sessions = today_sessions.filter(Course.teacher_user_id == current_user.id)
    today_sessions_count = today_sessions.count()

    month_start = date(today.year, today.month, 1)
    attendance_query = Attendance.query.join(Session).filter(
        Session.session_date >= month_start,
        Session.lesson_delivered == True
    )
    if current_user.role == "teacher":
        attendance_query = attendance_query.join(Course, Session.course_id == Course.id).filter(
            Course.id.in_(teacher_course_ids)
        )
    total_attendance = attendance_query.count()
    attended_attendance = attendance_query.filter(Attendance.status.in_(["present", "late", "excused"])).count()
    attendance_rate = round((attended_attendance / total_attendance) * 100, 2) if total_attendance else 0

    if current_user.role == "teacher":
        active_teachers = 1
    else:
        active_teachers = db.session.query(Teacher).outerjoin(User, Teacher.user_id == User.id).filter(
            (Teacher.user_id == None) | (User.is_active == True)
        ).count()

    recent_enrollments_query = Enrollment.query
    if current_user.role == "teacher":
        recent_enrollments_query = recent_enrollments_query.join(Course, Enrollment.course_id == Course.id).filter(
            Course.id.in_(teacher_course_ids)
        )
    recent_enrollments = recent_enrollments_query.order_by(Enrollment.enrolled_at.desc()).limit(6).all()

    teacher_attendance_labels = []
    teacher_attended_counts = []
    teacher_absent_counts = []
    if current_user.role == "teacher":
        recent_sessions = Session.query.join(Course).filter(
            Course.id.in_(teacher_course_ids),
            Session.lesson_delivered == True
        ).order_by(Session.session_date.desc()).limit(6).all()
        session_ids = [s.id for s in recent_sessions]
        attendance_counts = {}
        if session_ids:
            rows = db.session.query(
                Attendance.session_id,
                Attendance.status,
                func.count(Attendance.id)
            ).filter(Attendance.session_id.in_(session_ids)).group_by(
                Attendance.session_id,
                Attendance.status
            ).all()
            for session_id, status, count in rows:
                attendance_counts.setdefault(session_id, {})[status] = count
        for session in reversed(recent_sessions):
            label = session.session_date.strftime("%d.%m")
            counts = attendance_counts.get(session.id, {})
            attended = counts.get("present", 0) + counts.get("late", 0) + counts.get("excused", 0)
            absent = counts.get("absent", 0)
            teacher_attendance_labels.append(label)
            teacher_attended_counts.append(attended)
            teacher_absent_counts.append(absent)

    return render_template(
        "dashboard.html",
        active_courses=active_courses,
        total_students=total_students,
        today_sessions_count=today_sessions_count,
        total_attendance=total_attendance,
        attendance_rate=attendance_rate,
        active_teachers=active_teachers,
        recent_enrollments=recent_enrollments,
        teacher_attendance_labels=teacher_attendance_labels,
        teacher_attended_counts=teacher_attended_counts,
        teacher_absent_counts=teacher_absent_counts
    )

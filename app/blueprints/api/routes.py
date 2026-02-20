from datetime import datetime, date, time, timedelta
from flask import Blueprint, jsonify, request, g
from sqlalchemy import func
from flask_login import current_user
from ...extensions import db
from ...models import Course, Enrollment, Session, Attendance, Teacher, Organization, CourseType, Location, Student, PreRegistration
from ...security import require_api_roles, require_api_user, authenticate_api_token
from ...services.notifications import emit_webhook


api_bp = Blueprint("api", __name__)


def _course_query_for_user(user):
    query = Course.query.filter(Course.status == "active")
    if user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        if teacher:
            query = query.filter(Course.teacher_id == teacher.id)
        else:
            query = query.filter_by(teacher_user_id=user.id)
    return query


def _first_day_next_month(month_start):
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)


def _resolve_month_range(month_raw):
    if month_raw:
        try:
            month_start = datetime.strptime(month_raw, "%Y-%m").date().replace(day=1)
        except ValueError:
            return None, None, {"error": "invalid_month", "expected": "YYYY-MM"}
    else:
        first_of_current_month = date.today().replace(day=1)
        last_day_previous_month = first_of_current_month - timedelta(days=1)
        month_start = last_day_previous_month.replace(day=1)
    month_end_exclusive = _first_day_next_month(month_start)
    return month_start, month_end_exclusive, None


@api_bp.route("/webhooks/n8n/test", methods=["POST"])
@require_api_roles("admin")
def n8n_test():
    payload = {
        "event_type": "test",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_user_id": g.api_user.id,
        "data": {"message": "n8n test"}
    }
    result = emit_webhook("test", payload)
    return jsonify(result)


@api_bp.route("/courses", methods=["GET"])
@require_api_user()
def list_courses():
    courses = _course_query_for_user(g.api_user).all()
    return jsonify([{"id": c.id, "title": c.title, "status": c.status} for c in courses])


@api_bp.route("/courses", methods=["POST"])
@require_api_roles("coordinator", "principal", "attache", "admin")
def create_course():
    data = request.json or {}
    start_date = date.fromisoformat(data.get("start_date")) if data.get("start_date") else None
    end_date = date.fromisoformat(data.get("end_date")) if data.get("end_date") else None
    if not start_date or not end_date:
        return jsonify({"error": "missing_dates"}), 400
    teacher_id = data.get("teacher_id")
    teacher_user_id = None
    teacher_name_cached = None
    if teacher_id:
        teacher = Teacher.query.get(teacher_id)
        teacher_user_id = teacher.user_id if teacher else None
        teacher_name_cached = teacher.full_name if teacher else None
    organization = Organization.query.get(data.get("organization_id")) if data.get("organization_id") else None
    course_type = CourseType.query.get(data.get("course_type_id")) if data.get("course_type_id") else None
    location = Location.query.get(data.get("location_id")) if data.get("location_id") else None
    course = Course(
        organization_id=data.get("organization_id"),
        course_type_id=data.get("course_type_id"),
        location_id=data.get("location_id"),
        teacher_id=teacher_id,
        teacher_user_id=teacher_user_id,
        teacher_name_cached=teacher_name_cached,
        organization_name_cached=organization.name if organization else None,
        course_type_name_cached=course_type.name if course_type else None,
        location_name_cached=location.name if location else None,
        title=data.get("title"),
        start_date=start_date,
        end_date=end_date,
        schedule_json=data.get("schedule_json"),
        capacity=data.get("capacity"),
        status="active",
        created_by_user_id=g.api_user.id
    )
    db.session.add(course)
    db.session.commit()
    return jsonify({"id": course.id}), 201


@api_bp.route("/courses/<int:course_id>/enroll", methods=["POST"])
@require_api_roles("coordinator", "principal", "attache", "admin")
def enroll(course_id):
    student_id = request.json.get("student_id")
    existing = Enrollment.query.filter_by(course_id=course_id, student_id=student_id).first()
    if existing:
        return jsonify({"error": "already_enrolled"}), 400
    active_enrollment = Enrollment.query.filter(
        Enrollment.student_id == student_id,
        Enrollment.status == "active"
    ).first()
    if active_enrollment:
        return jsonify({"error": "active_enrollment_exists"}), 400
    enrollment = Enrollment(course_id=course_id, student_id=student_id)
    db.session.add(enrollment)
    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.route("/sessions/<int:session_id>/attendance", methods=["POST"])
@require_api_roles("teacher", "coordinator", "principal", "attache", "admin")
def attendance(session_id):
    data = request.json or {}
    lesson_delivered = data.get("lesson_delivered")
    if lesson_delivered is not None:
        session = Session.query.get_or_404(session_id)
        session.lesson_delivered = bool(lesson_delivered)
        db.session.add(session)
        if not session.lesson_delivered:
            db.session.commit()
            return jsonify({"status": "ok", "lesson_delivered": False})
    for row in data.get("attendance", []):
        student_id = row.get("student_id")
        status = row.get("status")
        note = row.get("note")
        existing = Attendance.query.filter_by(session_id=session_id, student_id=student_id).first()
        if existing:
            existing.status = status
            existing.note = note
            existing.marked_by_user_id = g.api_user.id
        else:
            db.session.add(Attendance(
                session_id=session_id,
                student_id=student_id,
                status=status,
                note=note,
                marked_by_user_id=g.api_user.id
            ))
    db.session.commit()
    emit_webhook("session_attendance_submitted", {
        "event_type": "session_attendance_submitted",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_user_id": g.api_user.id,
        "session_id": session_id
    })
    return jsonify({"status": "ok"})


@api_bp.route("/stats/summary", methods=["GET"])
@require_api_user()
def summary():
    active_courses = _course_query_for_user(g.api_user).filter(Course.status == "active").count()
    return jsonify({"active_courses": active_courses})


@api_bp.route("/reports/daily-course-sessions", methods=["GET"])
def daily_course_sessions():
    user = authenticate_api_token()
    if user:
        if user.role != "admin":
            return jsonify({"error": "forbidden"}), 403
    else:
        if current_user.is_authenticated and current_user.role == "admin":
            user = current_user
        elif current_user.is_authenticated:
            return jsonify({"error": "forbidden"}), 403
        else:
            return jsonify({"error": "unauthorized"}), 401
    g.api_user = user

    raw_date = (request.args.get("date") or "").strip()
    if raw_date:
        try:
            target_date = date.fromisoformat(raw_date)
        except ValueError:
            return jsonify({"error": "invalid_date", "expected": "YYYY-MM-DD"}), 400
    else:
        target_date = date.today()

    base_course_query = _course_query_for_user(g.api_user).with_entities(Course.id)
    sessions = (
        db.session.query(Session, Course)
        .join(Course, Course.id == Session.course_id)
        .filter(Session.session_date == target_date)
        .filter(Course.status == "active")
        .filter(Course.id.in_(base_course_query))
        .order_by(Course.title.asc(), Session.start_time.asc(), Session.id.asc())
        .all()
    )

    session_ids = [session.id for session, _ in sessions]
    attendance_rows = []
    if session_ids:
        attendance_rows = (
            db.session.query(
                Attendance.session_id,
                Attendance.status,
                func.count(Attendance.id).label("count")
            )
            .filter(Attendance.session_id.in_(session_ids))
            .group_by(Attendance.session_id, Attendance.status)
            .all()
        )

    attendance_map = {}
    for session_id, status, count in attendance_rows:
        bucket = attendance_map.setdefault(session_id, {"present": 0, "absent": 0, "late": 0, "excused": 0})
        if status in bucket:
            bucket[status] = int(count)

    course_map = {}
    for session, course in sessions:
        course_item = course_map.setdefault(course.id, {
            "course_id": course.id,
            "course_title": course.title,
            "course_status": course.status,
            "start_date": course.start_date.isoformat() if course.start_date else None,
            "end_date": course.end_date.isoformat() if course.end_date else None,
            "teacher_name": course.teacher.full_name if course.teacher else (course.teacher_name_cached or "-"),
            "sessions": []
        })
        counts = attendance_map.get(session.id, {"present": 0, "absent": 0, "late": 0, "excused": 0})
        total_marked = counts["present"] + counts["absent"] + counts["late"] + counts["excused"]
        course_item["sessions"].append({
            "session_id": session.id,
            "session_date": session.session_date.isoformat() if session.session_date else None,
            "start_time": session.start_time.strftime("%H:%M") if session.start_time else None,
            "end_time": session.end_time.strftime("%H:%M") if session.end_time else None,
            "lesson_delivered": bool(session.lesson_delivered),
            "attendance_submitted": total_marked > 0,
            "attendance_counts": counts,
            "attendance_total_marked": total_marked
        })

    courses = list(course_map.values())
    total_sessions = sum(len(item["sessions"]) for item in courses)
    totals = {"present": 0, "absent": 0, "late": 0, "excused": 0}
    delivered_count = 0
    submitted_count = 0
    for item in courses:
        for session in item["sessions"]:
            if session["lesson_delivered"]:
                delivered_count += 1
            if session["attendance_submitted"]:
                submitted_count += 1
            totals["present"] += session["attendance_counts"]["present"]
            totals["absent"] += session["attendance_counts"]["absent"]
            totals["late"] += session["attendance_counts"]["late"]
            totals["excused"] += session["attendance_counts"]["excused"]

    total_active_courses = Course.query.filter(Course.status == "active").count()
    total_active_teachers = (
        db.session.query(func.count(func.distinct(Course.teacher_id)))
        .filter(Course.status == "active", Course.teacher_id.isnot(None))
        .scalar() or 0
    )
    total_active_students = (
        db.session.query(func.count(func.distinct(Enrollment.student_id)))
        .join(Course, Course.id == Enrollment.course_id)
        .join(Student, Student.id == Enrollment.student_id)
        .filter(
            Enrollment.status == "active",
            Course.status == "active",
            Student.is_active.is_(True)
        )
        .scalar() or 0
    )
    total_active_organizations = (
        db.session.query(func.count(func.distinct(Course.organization_id)))
        .filter(Course.status == "active", Course.organization_id.isnot(None))
        .scalar() or 0
    )
    pending_pre_registrations = PreRegistration.query.filter(PreRegistration.status == "pending").count()
    day_start = datetime.combine(target_date, time.min)
    day_end = day_start + timedelta(days=1)
    new_students_today_count = (
        Student.query
        .filter(
            Student.is_active.is_(True),
            Student.created_at >= day_start,
            Student.created_at < day_end
        )
        .count()
    )
    attendance_total_all = totals["present"] + totals["absent"] + totals["late"] + totals["excused"]
    avg_attendance_rate = round((totals["present"] / attendance_total_all) * 100, 2) if attendance_total_all > 0 else 0.0

    payload = {
        "report_type": "daily_course_sessions",
        "date": target_date.isoformat(),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_courses_count": total_active_courses,
        "total_teachers_count": int(total_active_teachers),
        "total_students_count": int(total_active_students),
        "total_organizations_count": int(total_active_organizations),
        "pending_pre_registrations_count": int(pending_pre_registrations),
        "new_students_today_count": int(new_students_today_count),
        "courses_count": len(courses),
        "sessions_count": total_sessions,
        "lesson_delivered_count": delivered_count,
        "attendance_submitted_sessions_count": submitted_count,
        "avg_attendance_rate": avg_attendance_rate,
        "attendance_totals": totals,
        "courses": courses
    }
    return jsonify(payload)


@api_bp.route("/reports/monthly-course-sessions", methods=["GET"])
def monthly_course_sessions():
    user = authenticate_api_token()
    if user:
        if user.role != "admin":
            return jsonify({"error": "forbidden"}), 403
    else:
        if current_user.is_authenticated and current_user.role == "admin":
            user = current_user
        elif current_user.is_authenticated:
            return jsonify({"error": "forbidden"}), 403
        else:
            return jsonify({"error": "unauthorized"}), 401
    g.api_user = user

    month_start, month_end_exclusive, month_error = _resolve_month_range((request.args.get("month") or "").strip())
    if month_error:
        return jsonify(month_error), 400

    base_course_query = _course_query_for_user(g.api_user).with_entities(Course.id)
    sessions = (
        db.session.query(Session, Course)
        .join(Course, Course.id == Session.course_id)
        .filter(Session.session_date >= month_start)
        .filter(Session.session_date < month_end_exclusive)
        .filter(Course.status == "active")
        .filter(Course.id.in_(base_course_query))
        .order_by(Course.title.asc(), Session.session_date.asc(), Session.start_time.asc(), Session.id.asc())
        .all()
    )

    session_ids = [session.id for session, _ in sessions]
    attendance_rows = []
    if session_ids:
        attendance_rows = (
            db.session.query(
                Attendance.session_id,
                Attendance.status,
                func.count(Attendance.id).label("count")
            )
            .filter(Attendance.session_id.in_(session_ids))
            .group_by(Attendance.session_id, Attendance.status)
            .all()
        )

    attendance_map = {}
    for session_id, status, count in attendance_rows:
        bucket = attendance_map.setdefault(session_id, {"present": 0, "absent": 0, "late": 0, "excused": 0})
        if status in bucket:
            bucket[status] = int(count)

    course_map = {}
    for session, course in sessions:
        course_item = course_map.setdefault(course.id, {
            "course_id": course.id,
            "course_title": course.title,
            "course_status": course.status,
            "start_date": course.start_date.isoformat() if course.start_date else None,
            "end_date": course.end_date.isoformat() if course.end_date else None,
            "teacher_name": course.teacher.full_name if course.teacher else (course.teacher_name_cached or "-"),
            "sessions": []
        })
        counts = attendance_map.get(session.id, {"present": 0, "absent": 0, "late": 0, "excused": 0})
        total_marked = counts["present"] + counts["absent"] + counts["late"] + counts["excused"]
        course_item["sessions"].append({
            "session_id": session.id,
            "session_date": session.session_date.isoformat() if session.session_date else None,
            "start_time": session.start_time.strftime("%H:%M") if session.start_time else None,
            "end_time": session.end_time.strftime("%H:%M") if session.end_time else None,
            "lesson_delivered": bool(session.lesson_delivered),
            "attendance_submitted": total_marked > 0,
            "attendance_counts": counts,
            "attendance_total_marked": total_marked
        })

    courses = list(course_map.values())
    total_sessions = sum(len(item["sessions"]) for item in courses)
    totals = {"present": 0, "absent": 0, "late": 0, "excused": 0}
    delivered_count = 0
    submitted_count = 0
    for item in courses:
        for session in item["sessions"]:
            if session["lesson_delivered"]:
                delivered_count += 1
            if session["attendance_submitted"]:
                submitted_count += 1
            totals["present"] += session["attendance_counts"]["present"]
            totals["absent"] += session["attendance_counts"]["absent"]
            totals["late"] += session["attendance_counts"]["late"]
            totals["excused"] += session["attendance_counts"]["excused"]

    total_active_courses = Course.query.filter(Course.status == "active").count()
    total_active_teachers = (
        db.session.query(func.count(func.distinct(Course.teacher_id)))
        .filter(Course.status == "active", Course.teacher_id.isnot(None))
        .scalar() or 0
    )
    total_active_students = (
        db.session.query(func.count(func.distinct(Enrollment.student_id)))
        .join(Course, Course.id == Enrollment.course_id)
        .join(Student, Student.id == Enrollment.student_id)
        .filter(
            Enrollment.status == "active",
            Course.status == "active",
            Student.is_active.is_(True)
        )
        .scalar() or 0
    )
    total_active_organizations = (
        db.session.query(func.count(func.distinct(Course.organization_id)))
        .filter(Course.status == "active", Course.organization_id.isnot(None))
        .scalar() or 0
    )
    pending_pre_registrations = PreRegistration.query.filter(PreRegistration.status == "pending").count()
    attendance_total_all = totals["present"] + totals["absent"] + totals["late"] + totals["excused"]
    avg_attendance_rate = round((totals["present"] / attendance_total_all) * 100, 2) if attendance_total_all > 0 else 0.0

    payload = {
        "report_type": "monthly_course_sessions",
        "month": month_start.strftime("%Y-%m"),
        "period_start": month_start.isoformat(),
        "period_end": (month_end_exclusive - timedelta(days=1)).isoformat(),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_courses_count": int(total_active_courses),
        "total_teachers_count": int(total_active_teachers),
        "total_students_count": int(total_active_students),
        "total_organizations_count": int(total_active_organizations),
        "pending_pre_registrations_count": int(pending_pre_registrations),
        "courses_count": len(courses),
        "sessions_count": total_sessions,
        "lesson_delivered_count": delivered_count,
        "attendance_submitted_sessions_count": submitted_count,
        "avg_attendance_rate": avg_attendance_rate,
        "attendance_totals": totals,
        "courses": courses
    }
    return jsonify(payload)

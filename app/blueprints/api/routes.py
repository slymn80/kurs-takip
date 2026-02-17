from datetime import datetime, date
from flask import Blueprint, jsonify, request, g
from ...extensions import db
from ...models import Course, Enrollment, Session, Attendance, Teacher, Organization, CourseType, Location
from ...security import require_api_roles, require_api_user
from ...services.notifications import emit_webhook


api_bp = Blueprint("api", __name__)


def _course_query_for_user(user):
    query = Course.query
    if user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        if teacher:
            query = query.filter(Course.teacher_id == teacher.id)
        else:
            query = query.filter_by(teacher_user_id=user.id)
    return query


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

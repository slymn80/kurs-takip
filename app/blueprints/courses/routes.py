import io
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file
from flask_login import login_required, current_user
from sqlalchemy import and_, or_
from ...extensions import db
from ...models import Course, Organization, CourseType, Location, Teacher, User, Student, Enrollment, Session, Attendance, AuditLog
from ...forms import CourseForm, SessionForm
from ...security import require_roles
from ...utils import generate_sessions, serialize_json, absence_ratio
from ...services.settings import get_setting
from ...services.notifications import emit_webhook, send_whatsapp


courses_bp = Blueprint("courses", __name__)


def _course_query_for_user():
    query = Course.query
    if current_user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        if teacher:
            query = query.filter(or_(Course.teacher_id == teacher.id, Course.teacher_user_id == current_user.id))
        else:
            query = query.filter_by(teacher_user_id=current_user.id)
    return query


@courses_bp.route("/")
@login_required
def list_courses():
    query = _course_query_for_user()
    items = query.filter(Course.status == "active").order_by(Course.created_at.desc()).all()
    return render_template("courses/list.html", items=items)


@courses_bp.route("/completed")
@login_required
def completed_courses():
    query = _course_query_for_user()
    items = query.filter(Course.status != "active").order_by(Course.created_at.desc()).all()
    return render_template("courses/completed.html", items=items)


@courses_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def new_course():
    form = CourseForm()
    form.organization_id.choices = [(o.id, o.name) for o in Organization.query.order_by(Organization.name).all()]
    form.course_type_id.choices = [(c.id, c.name) for c in CourseType.query.order_by(CourseType.name).all()]
    form.location_id.choices = [(l.id, l.name) for l in Location.query.order_by(Location.name).all()]
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    form.teacher_id.choices = [(t.id, t.full_name) for t in teachers]
    if current_user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        if teacher:
            form.teacher_id.data = teacher.id

    if form.validate_on_submit():
        selected_teacher = Teacher.query.get(form.teacher_id.data)
        if not selected_teacher:
            flash("Lütfen bir öğretmen seçin.", "error")
            return render_template("courses/new.html", form=form)
        teacher_user_id = selected_teacher.user_id if selected_teacher and selected_teacher.user_id else None
        schedule_days = request.form.getlist("schedule_days")
        schedule = {
            "days": schedule_days,
            "start_time": form.start_time.data.isoformat() if form.start_time.data else None,
            "end_time": form.end_time.data.isoformat() if form.end_time.data else None
        }
        course = Course(
            organization_id=form.organization_id.data,
            course_type_id=form.course_type_id.data,
            location_id=form.location_id.data,
            teacher_id=form.teacher_id.data,
            teacher_user_id=teacher_user_id,
            title=form.title.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            schedule_json=schedule,
            capacity=form.capacity.data,
            status="active",
            created_by_user_id=current_user.id
        )
        db.session.add(course)
        db.session.flush()
        sessions = generate_sessions(form.start_date.data, form.end_date.data, schedule_days)
        for session_date in sessions:
            db.session.add(Session(
                course_id=course.id,
                session_date=session_date,
                start_time=form.start_time.data,
                end_time=form.end_time.data,
                lesson_delivered=True
            ))
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="course", entity_id=course.id, after_json=serialize_json({"title": course.title})))
        db.session.commit()

        emit_webhook("course_created", {
            "event_type": "course_created",
            "timestamp": datetime.utcnow().isoformat(),
            "actor_user_id": current_user.id,
            "course_id": course.id,
            "data": {"title": course.title}
        })

        flash("Kurs başlatıldı.", "success")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    return render_template("courses/new.html", form=form)


@courses_bp.route("/<int:course_id>")
@login_required
def course_detail(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    enrollments = Enrollment.query.filter_by(course_id=course.id).all()
    sessions = Session.query.filter_by(course_id=course.id).order_by(Session.session_date.asc()).all()
    students = Student.query.order_by(Student.full_name).all()
    return render_template("courses/detail.html", course=course, enrollments=enrollments, sessions=sessions, students=students)


@courses_bp.route("/<int:course_id>/enroll", methods=["POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def enroll_student(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    student_id = int(request.form.get("student_id"))
    existing = Enrollment.query.filter_by(course_id=course.id, student_id=student_id).first()
    if existing:
        flash("Bu kursiyer zaten kayitli.", "error")
        return redirect(url_for("courses.course_detail", course_id=course.id))
    enrollment = Enrollment(course_id=course.id, student_id=student_id)
    db.session.add(enrollment)
    db.session.add(AuditLog(actor_user_id=current_user.id, action="enroll", entity_type="course", entity_id=course.id, after_json=serialize_json({"student_id": student_id})))
    db.session.commit()
    flash("Kursiyer eklendi.", "success")
    return redirect(url_for("courses.course_detail", course_id=course.id))


@courses_bp.route("/<int:course_id>/enrollments/<int:student_id>/delete", methods=["POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def remove_enrollment(course_id, student_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    enrollment = Enrollment.query.filter_by(course_id=course.id, student_id=student_id).first_or_404()
    db.session.delete(enrollment)
    db.session.add(AuditLog(actor_user_id=current_user.id, action="unenroll", entity_type="course", entity_id=course.id, after_json=serialize_json({"student_id": student_id})))
    db.session.commit()
    flash("Kursiyer çıkarıldı.", "success")
    return redirect(url_for("courses.course_detail", course_id=course.id))


@courses_bp.route("/<int:course_id>/status", methods=["POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def update_status(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    status = request.form.get("status")
    allowed = {"ended", "dropped", "cancelled", "updated", "archived"}
    if status not in allowed:
        flash("Geçersiz durum seçimi.", "error")
        return redirect(url_for("courses.list_courses"))
    course.status = status
    db.session.add(AuditLog(actor_user_id=current_user.id, action="status_update", entity_type="course", entity_id=course.id, after_json=serialize_json({"status": status})))
    db.session.commit()
    flash("Kurs durumu güncellendi.", "success")
    return redirect(url_for("courses.completed_courses"))


@courses_bp.route("/<int:course_id>/sessions/new", methods=["GET", "POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def new_session(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    form = SessionForm()
    if form.validate_on_submit():
        session = Session(
            course_id=course.id,
            session_date=form.session_date.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            topic=form.topic.data,
            lesson_delivered=True
        )
        db.session.add(session)
        db.session.commit()
        flash("Oturum eklendi.", "success")
        return redirect(url_for("courses.course_detail", course_id=course.id))
    return render_template("courses/new_session.html", form=form, course=course)


@courses_bp.route("/sessions/<int:session_id>/attendance", methods=["GET", "POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def take_attendance(session_id):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    enrollments = Enrollment.query.filter_by(course_id=course.id, status="active").all()

    if request.method == "POST":
        lesson_delivered = bool(request.form.get("lesson_delivered"))
        session.lesson_delivered = lesson_delivered
        db.session.add(session)
        if not lesson_delivered:
            db.session.commit()
            flash("Ders işlenmedi olarak kaydedildi.", "success")
            return redirect(url_for("courses.course_detail", course_id=course.id))

        for enrollment in enrollments:
            status = request.form.get(f"status_{enrollment.student_id}")
            note = request.form.get(f"note_{enrollment.student_id}")
            if not status:
                continue
            existing = Attendance.query.filter_by(session_id=session.id, student_id=enrollment.student_id).first()
            if existing:
                existing.status = status
                existing.note = note
                existing.marked_by_user_id = current_user.id
            else:
                db.session.add(Attendance(
                    session_id=session.id,
                    student_id=enrollment.student_id,
                    status=status,
                    note=note,
                    marked_by_user_id=current_user.id
                ))
        db.session.commit()

        threshold_value = get_setting("absence_threshold_ratio", "0.2")
        try:
            threshold = float(threshold_value)
        except ValueError:
            threshold = 0.2

        total_sessions = Session.query.filter_by(course_id=course.id, lesson_delivered=True).count()
        for enrollment in enrollments:
            absent_count = Attendance.query.join(Session).filter(
                Session.course_id == course.id,
                Session.lesson_delivered == True,
                Attendance.student_id == enrollment.student_id,
                Attendance.status == "absent"
            ).count()
            if total_sessions and absence_ratio(absent_count, total_sessions) >= threshold:
                payload = {
                    "event_type": "absence_threshold_exceeded",
                    "timestamp": datetime.utcnow().isoformat(),
                    "actor_user_id": current_user.id,
                    "course_id": course.id,
                    "student_id": enrollment.student_id,
                    "data": {"absent_count": absent_count, "total_sessions": total_sessions}
                }
                emit_webhook("absence_threshold_exceeded", payload)
                if enrollment.student.phone:
                    send_whatsapp("Devamsızlık eşiği aşıldı. Lütfen kurs ile iletişime geçin.", enrollment.student.phone)

        emit_webhook("session_attendance_submitted", {
            "event_type": "session_attendance_submitted",
            "timestamp": datetime.utcnow().isoformat(),
            "actor_user_id": current_user.id,
            "course_id": course.id,
            "session_id": session.id,
            "data": {"session_date": session.session_date.isoformat()}
        })
        flash("Yoklama kaydedildi.", "success")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    existing_attendance = {a.student_id: a for a in Attendance.query.filter_by(session_id=session.id).all()}
    return render_template("courses/attendance.html", course=course, session=session, enrollments=enrollments, existing_attendance=existing_attendance)


@courses_bp.route("/<int:course_id>/attendance.csv")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def export_attendance(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    rows = []
    rows.append("session_date,student_name,status,note")
    for session in Session.query.filter_by(course_id=course.id, lesson_delivered=True).all():
        for attendance in Attendance.query.filter_by(session_id=session.id).all():
            rows.append(f"{session.session_date},{attendance.student.full_name},{attendance.status},{attendance.note or ''}")
    csv_content = "\n".join(rows)
    return send_file(
        io.BytesIO(csv_content.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"attendance_course_{course.id}.csv"
    )

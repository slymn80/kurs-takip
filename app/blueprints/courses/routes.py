import io
import os
import secrets
import qrcode
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, request, flash, send_file, abort
from flask_login import login_required, current_user
from sqlalchemy import and_, or_, func
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from ...extensions import db, bcrypt
from ...models import Course, Organization, CourseType, Location, Teacher, User, Student, Enrollment, Session, Attendance, AuditLog, CourseExamResult, AttendanceQrToken
from ...forms import CourseForm, SessionForm
from ...security import require_roles
from ...utils import generate_sessions, serialize_json, absence_ratio
from ...services.settings import get_setting
from ...services.notifications import emit_webhook, send_whatsapp


courses_bp = Blueprint("courses", __name__)


def _pdf_font_name():
    candidates = [
        ("Arial", r"C:\Windows\Fonts\arial.ttf"),
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return "Helvetica"


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
    items = query.filter(Course.status.in_(["ended", "cancelled", "archived"])).order_by(Course.created_at.desc()).all()
    return render_template("courses/completed.html", items=items)


@courses_bp.route("/cancelled")
@login_required
def cancelled_courses():
    query = _course_query_for_user()
    items = query.filter(Course.status == "dropped").order_by(Course.created_at.desc()).all()
    return render_template("courses/cancelled.html", items=items)


@courses_bp.route("/my-students")
@login_required
@require_roles("teacher")
def my_students():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    course_filters = [Course.teacher_user_id == current_user.id]
    if teacher:
        course_filters = [or_(Course.teacher_id == teacher.id, Course.teacher_user_id == current_user.id)]

    allowed_courses = (
        Course.query
        .filter(*course_filters)
        .order_by(Course.created_at.desc())
        .all()
    )
    allowed_course_ids = {c.id for c in allowed_courses}
    selected_course_id = request.args.get("course_id", type=int)
    if selected_course_id and selected_course_id not in allowed_course_ids:
        selected_course_id = None

    rows = (
        db.session.query(Enrollment, Student, Course)
        .join(Student, Enrollment.student_id == Student.id)
        .join(Course, Enrollment.course_id == Course.id)
        .filter(*course_filters)
        .filter(Course.id == selected_course_id if selected_course_id else True)
        .filter(Enrollment.status == "active")
        .order_by(Student.full_name.asc(), Course.title.asc())
        .all()
    )
    return render_template(
        "courses/my_students.html",
        rows=rows,
        courses=allowed_courses,
        selected_course_id=selected_course_id
    )


@courses_bp.route("/students/<int:student_id>")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def student_detail(student_id):
    if current_user.role == "teacher":
        allowed_course_ids = [c.id for c in _course_query_for_user().with_entities(Course.id).all()]
        has_access = Enrollment.query.filter(
            Enrollment.student_id == student_id,
            Enrollment.course_id.in_(allowed_course_ids)
        ).first()
        if not has_access:
            abort(404)
    student = Student.query.get_or_404(student_id)
    return render_template("courses/student_detail.html", student=student)


@courses_bp.route("/new", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def new_course():
    form = CourseForm()
    form.organization_id.choices = [(o.id, o.name) for o in Organization.query.order_by(Organization.name).all()]
    form.course_type_id.choices = [(c.id, c.name) for c in CourseType.query.order_by(CourseType.name).all()]
    form.location_id.choices = [(l.id, l.name) for l in Location.query.order_by(Location.name).all()]
    teacher_users = User.query.filter_by(role="teacher").order_by(User.full_name).all()
    form.teacher_user_id.choices = [(0, "Öğretmen yok")] + [(u.id, u.full_name) for u in teacher_users]
    if current_user.role == "teacher":
        form.teacher_user_id.data = current_user.id

    if form.validate_on_submit():
        selected_user = User.query.get(form.teacher_user_id.data) if form.teacher_user_id.data else None
        linked_teacher = Teacher.query.filter_by(user_id=selected_user.id).first() if selected_user else None
        teacher_user_id = selected_user.id if selected_user else None
        selected_org = Organization.query.get(form.organization_id.data) if form.organization_id.data else None
        selected_type = CourseType.query.get(form.course_type_id.data) if form.course_type_id.data else None
        selected_loc = Location.query.get(form.location_id.data) if form.location_id.data else None
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
            teacher_id=linked_teacher.id if linked_teacher else None,
            teacher_user_id=teacher_user_id,
            teacher_name_cached=selected_user.full_name if selected_user else None,
            organization_name_cached=selected_org.name if selected_org else None,
            course_type_name_cached=selected_type.name if selected_type else None,
            location_name_cached=selected_loc.name if selected_loc else None,
            title=form.title.data,
            term=form.term.data,
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
                lesson_delivered=False
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

@courses_bp.route("/<int:course_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def edit_course(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    form = CourseForm(obj=course)
    form.organization_id.choices = [(o.id, o.name) for o in Organization.query.order_by(Organization.name).all()]
    form.course_type_id.choices = [(c.id, c.name) for c in CourseType.query.order_by(CourseType.name).all()]
    form.location_id.choices = [(l.id, l.name) for l in Location.query.order_by(Location.name).all()]
    teacher_users = User.query.filter_by(role="teacher").order_by(User.full_name).all()
    form.teacher_user_id.choices = [(0, "Öğretmen yok")] + [(u.id, u.full_name) for u in teacher_users]
    if course.teacher_user_id:
        form.teacher_user_id.data = course.teacher_user_id
    elif course.teacher_id:
        linked = Teacher.query.get(course.teacher_id)
        form.teacher_user_id.data = linked.user_id if linked and linked.user_id else 0
    else:
        form.teacher_user_id.data = 0

    if form.validate_on_submit():
        selected_user = User.query.get(form.teacher_user_id.data) if form.teacher_user_id.data else None
        linked_teacher = Teacher.query.filter_by(user_id=selected_user.id).first() if selected_user else None
        teacher_user_id = selected_user.id if selected_user else None
        selected_org = Organization.query.get(form.organization_id.data) if form.organization_id.data else None
        selected_type = CourseType.query.get(form.course_type_id.data) if form.course_type_id.data else None
        selected_loc = Location.query.get(form.location_id.data) if form.location_id.data else None
        schedule_days = request.form.getlist("schedule_days")
        schedule = {
            "days": schedule_days,
            "start_time": form.start_time.data.isoformat() if form.start_time.data else None,
            "end_time": form.end_time.data.isoformat() if form.end_time.data else None
        }
        course.organization_id = form.organization_id.data
        course.course_type_id = form.course_type_id.data
        course.location_id = form.location_id.data
        course.teacher_id = linked_teacher.id if linked_teacher else None
        course.teacher_user_id = teacher_user_id
        course.teacher_name_cached = selected_user.full_name if selected_user else None
        course.organization_name_cached = selected_org.name if selected_org else None
        course.course_type_name_cached = selected_type.name if selected_type else None
        course.location_name_cached = selected_loc.name if selected_loc else None
        course.title = form.title.data
        course.term = form.term.data
        course.start_date = form.start_date.data
        course.end_date = form.end_date.data
        course.capacity = form.capacity.data
        course.schedule_json = schedule
        db.session.add(course)
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="update",
            entity_type="course",
            entity_id=course.id,
            after_json=serialize_json({"title": course.title})
        ))
        db.session.commit()
        flash("Kurs güncellendi.", "success")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    schedule_days_selected = set()
    if course.schedule_json and course.schedule_json.get("days"):
        schedule_days_selected = set(course.schedule_json.get("days", []))
    return render_template("courses/edit.html", form=form, course=course, schedule_days_selected=schedule_days_selected)

@courses_bp.route("/<int:course_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_course(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    password = request.form.get("password", "")
    if not bcrypt.check_password_hash(current_user.password_hash, password):
        flash("Åifre hatalÄ±.", "error")
        return redirect(request.referrer or url_for("courses.list_courses"))

    session_ids = [s.id for s in Session.query.filter_by(course_id=course.id).all()]
    if session_ids:
        Attendance.query.filter(Attendance.session_id.in_(session_ids)).delete(synchronize_session=False)
    Enrollment.query.filter_by(course_id=course.id).delete(synchronize_session=False)
    Session.query.filter_by(course_id=course.id).delete(synchronize_session=False)
    db.session.delete(course)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="delete",
        entity_type="course",
        entity_id=course.id,
        after_json=serialize_json({"title": course.title})
    ))
    db.session.commit()
    flash("Kurs silindi.", "success")
    return redirect(url_for("courses.list_courses"))


@courses_bp.route("/<int:course_id>")
@login_required
def course_detail(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    enrollments = (
        Enrollment.query
        .filter_by(course_id=course.id, status="active")
        .filter(Enrollment.student_id.isnot(None))
        .all()
    )
    sessions = Session.query.filter_by(course_id=course.id).order_by(Session.session_date.asc()).all()
    total_enrolled = len(enrollments)
    last_session = sessions[-1] if sessions else None
    exam_results = {}
    if enrollments:
        results = CourseExamResult.query.filter(
            CourseExamResult.enrollment_id.in_([e.id for e in enrollments])
        ).all()
        exam_results = {r.enrollment_id: r for r in results}
    session_ids = [s.id for s in sessions]
    attended_counts = {}
    if session_ids:
        rows = db.session.query(
            Attendance.session_id,
            func.count(Attendance.id)
        ).filter(
            Attendance.session_id.in_(session_ids),
            Attendance.status.in_(["present", "late", "excused"])
        ).group_by(Attendance.session_id).all()
        attended_counts = {session_id: count for session_id, count in rows}
    if current_user.role == "teacher":
        students = [e.student for e in enrollments if e.student and e.student.is_active]
    else:
        active_student_ids = db.session.query(Enrollment.student_id).filter(Enrollment.status == "active")
        students = (
            Student.query
            .filter(Student.is_active.is_(True))
            .filter(~Student.id.in_(active_student_ids))
            .order_by(Student.full_name)
            .all()
        )
    return render_template(
        "courses/detail.html",
        course=course,
        enrollments=enrollments,
        sessions=sessions,
        last_session=last_session,
        exam_results=exam_results,
        students=students,
        total_enrolled=total_enrolled,
        attended_counts=attended_counts
    )


@courses_bp.route("/<int:course_id>/exam-results", methods=["POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def save_exam_results(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    enrollments = (
        Enrollment.query
        .filter_by(course_id=course.id, status="active")
        .filter(Enrollment.student_id.isnot(None))
        .all()
    )
    missing_score = []
    changed = 0
    for enrollment in enrollments:
        score_raw = request.form.get(f"score_{enrollment.id}")
        status_raw = request.form.get(f"status_{enrollment.id}")
        if score_raw is None and status_raw is None:
            continue
        score = None
        if score_raw is not None and score_raw != "":
            try:
                score = float(score_raw)
            except ValueError:
                score = None
        passed = None
        if status_raw == "passed":
            if score is None:
                missing_score.append(enrollment.student.full_name)
                continue
            passed = True
        elif status_raw == "failed":
            passed = False

        result = CourseExamResult.query.filter_by(enrollment_id=enrollment.id).first()
        if not result:
            result = CourseExamResult(enrollment_id=enrollment.id)
        if score is not None:
            result.score = score
        if passed is not None:
            result.passed = passed
        result.evaluated_at = datetime.utcnow()
        result.evaluated_by_user_id = current_user.id
        db.session.add(result)
        changed += 1

    if missing_score:
        flash("Başarılı seçimi için sınav puanı girilmelidir: " + ", ".join(missing_score), "error")
        return redirect(url_for("courses.course_detail", course_id=course.id))

    if changed:
        db.session.commit()
        flash("Değerlendirmeler kaydedildi.", "success")
    else:
        flash("Kaydedilecek değerlendirme bulunamadı.", "info")
    return redirect(url_for("courses.course_detail", course_id=course.id))


@courses_bp.route("/<int:course_id>/enroll", methods=["POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def enroll_student(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    student_id = int(request.form.get("student_id") or 0)
    student = Student.query.filter_by(id=student_id, is_active=True).first()
    if not student:
        flash("Geçersiz kursiyer seçimi.", "error")
        return redirect(url_for("courses.course_detail", course_id=course.id))
    existing = Enrollment.query.filter_by(course_id=course.id, student_id=student_id).first()
    if existing:
        flash("Bu kursiyer zaten kay?tl?.", "error")
        return redirect(url_for("courses.course_detail", course_id=course.id))
    active_enrollment = Enrollment.query.filter(
        Enrollment.student_id == student_id,
        Enrollment.status == "active"
    ).first()
    if active_enrollment:
        flash("Kursiyer zaten aktif bir kursa kay?tl?.", "error")
        return redirect(url_for("courses.course_detail", course_id=course.id))
    enrollment = Enrollment(course_id=course.id, student_id=student_id)
    db.session.add(enrollment)
    db.session.add(AuditLog(actor_user_id=current_user.id, action="enroll", entity_type="course", entity_id=course.id, after_json=serialize_json({"student_id": student_id})))
    db.session.commit()
    flash("Kursiyer eklendi.", "success")
    return redirect(url_for("courses.course_detail", course_id=course.id))


@courses_bp.route("/<int:course_id>/enrollments/<int:student_id>/delete", methods=["POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def remove_enrollment(course_id, student_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    enrollment = Enrollment.query.filter_by(course_id=course.id, student_id=student_id).first_or_404()
    db.session.delete(enrollment)
    db.session.add(AuditLog(actor_user_id=current_user.id, action="unenroll", entity_type="course", entity_id=course.id, after_json=serialize_json({"student_id": student_id})))
    db.session.commit()
    flash("Kursiyer Ã§Ä±karÄ±ldÄ±.", "success")
    return redirect(url_for("courses.course_detail", course_id=course.id))


@courses_bp.route("/<int:course_id>/status", methods=["POST"])
@login_required
@require_roles("admin")
def update_status(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    status = request.form.get("status")
    allowed = {"ended", "dropped", "cancelled", "updated", "archived"}
    if status not in allowed:
        flash("GeÃ§ersiz durum seÃ§imi.", "error")
        return redirect(url_for("courses.list_courses"))
    course.status = status
    db.session.add(AuditLog(actor_user_id=current_user.id, action="status_update", entity_type="course", entity_id=course.id, after_json=serialize_json({"status": status})))
    db.session.commit()
    flash("Kurs durumu gÃ¼ncellendi.", "success")
    return redirect(url_for("courses.completed_courses"))


@courses_bp.route("/<int:course_id>/restore", methods=["POST"])
@login_required
@require_roles("admin")
def restore_course(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    password = request.form.get("password", "")
    if not bcrypt.check_password_hash(current_user.password_hash, password):
        flash("Åifre hatalÄ±.", "error")
        return redirect(request.referrer or url_for("courses.completed_courses"))
    course.status = "active"
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="restore",
        entity_type="course",
        entity_id=course.id,
        after_json=serialize_json({"status": "active"})
    ))
    db.session.commit()
    flash("Kurs tekrar aktif edildi.", "success")
    return redirect(request.referrer or url_for("courses.list_courses"))


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
            lesson_delivered=False
        )
        db.session.add(session)
        db.session.commit()
        flash("Oturum eklendi.", "success")
        return redirect(url_for("courses.course_detail", course_id=course.id))
    return render_template("courses/new_session.html", form=form, course=course)


@courses_bp.route("/sessions/<int:session_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def edit_session(session_id):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    form = SessionForm(obj=session)
    if form.validate_on_submit():
        session.session_date = form.session_date.data
        session.start_time = form.start_time.data
        session.end_time = form.end_time.data
        session.topic = form.topic.data
        db.session.add(session)
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="update",
            entity_type="session",
            entity_id=session.id,
            after_json=serialize_json({"session_date": str(session.session_date)})
        ))
        db.session.commit()
        flash("Oturum gÃ¼ncellendi.", "success")
        return redirect(url_for("courses.course_detail", course_id=course.id))
    return render_template("courses/edit_session.html", form=form, course=course, session=session)


@courses_bp.route("/sessions/<int:session_id>/delete", methods=["POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def delete_session(session_id):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    db.session.delete(session)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="delete",
        entity_type="session",
        entity_id=session.id
    ))
    db.session.commit()
    flash("Oturum silindi.", "success")
    return redirect(url_for("courses.course_detail", course_id=course.id))


@courses_bp.route("/sessions/<int:session_id>/attendance", methods=["GET", "POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def take_attendance(session_id):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    enrollments = Enrollment.query.filter_by(course_id=course.id, status="active").all()
    now = datetime.utcnow()
    active_qr = (
        AttendanceQrToken.query.filter(
            AttendanceQrToken.session_id == session.id,
            AttendanceQrToken.expires_at > now
        )
        .order_by(AttendanceQrToken.created_at.desc())
        .first()
    )

    if request.method == "POST":
        lesson_delivered = bool(request.form.get("lesson_delivered"))
        session.lesson_delivered = lesson_delivered
        db.session.add(session)
        if not lesson_delivered:
            db.session.commit()
            flash("Ders iÅŸlenmedi olarak kaydedildi.", "success")
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
                    send_whatsapp("DevamsÄ±zlÄ±k eÅŸiÄŸi aÅŸÄ±ldÄ±. LÃ¼tfen kurs ile iletiÅŸime geÃ§in.", enrollment.student.phone)

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
    return render_template(
        "courses/attendance.html",
        course=course,
        session=session,
        enrollments=enrollments,
        existing_attendance=existing_attendance,
        active_qr=active_qr
    )


@courses_bp.route("/sessions/<int:session_id>/attendance/status")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def attendance_status(session_id):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    rows = Attendance.query.filter_by(session_id=session.id).all()
    attendance = {}
    present_ids = []
    for row in rows:
        attendance[row.student_id] = {
            "status": row.status,
            "note": row.note or "",
            "marked_at": row.marked_at.isoformat() if row.marked_at else None
        }
        if row.status == "present":
            present_ids.append(row.student_id)
    return {"present_student_ids": present_ids, "attendance": attendance}


@courses_bp.route("/sessions/<int:session_id>/attendance/qr", methods=["POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def start_attendance_qr(session_id):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    token = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    qr_token = AttendanceQrToken(
        session_id=session.id,
        token=token,
        expires_at=expires_at,
        created_by_user_id=current_user.id
    )
    session.lesson_delivered = True
    db.session.add(session)
    db.session.add(qr_token)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="create",
        entity_type="attendance_qr",
        entity_id=session.id,
        after_json=serialize_json({"expires_at": expires_at.isoformat()})
    ))
    db.session.commit()
    flash("QR yoklama başlatıldı. 5 dakika geçerlidir.", "success")
    return redirect(url_for("courses.take_attendance", session_id=session.id))


@courses_bp.route("/sessions/<int:session_id>/attendance/qr-image/<token>")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def attendance_qr_image(session_id, token):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    qr_token = AttendanceQrToken.query.filter_by(session_id=session.id, token=token).first_or_404()
    if qr_token.expires_at <= datetime.utcnow():
        abort(404)
    checkin_url = url_for("public.attendance_checkin", token=token, _external=True)
    img = qrcode.make(checkin_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@courses_bp.route("/sessions/<int:session_id>/lesson-delivered", methods=["POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def update_lesson_delivered(session_id):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    session.lesson_delivered = bool(request.form.get("lesson_delivered"))
    db.session.add(session)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="lesson_delivered_update",
        entity_type="session",
        entity_id=session.id,
        after_json=serialize_json({"lesson_delivered": session.lesson_delivered})
    ))
    db.session.commit()
    return redirect(url_for("courses.course_detail", course_id=course.id))


@courses_bp.route("/sessions/<int:session_id>/attendance.pdf")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def attendance_pdf(session_id):
    session = Session.query.get_or_404(session_id)
    course = _course_query_for_user().filter_by(id=session.course_id).first_or_404()
    enrollments = Enrollment.query.filter_by(course_id=course.id, status="active").all()
    attendance_map = {a.student_id: a for a in Attendance.query.filter_by(session_id=session.id).all()}

    status_labels = {
        "present": "Mevcut",
        "absent": "Yok",
        "late": "GeÃ§ kaldÄ±",
        "excused": "Mazeretli"
    }

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = _pdf_font_name()
    c.setFont(font_name, 14)
    c.drawString(40, height - 40, "Yoklama Listesi")
    c.setFont(font_name, 10)
    c.drawString(40, height - 60, f"Kurs: {course.title}")
    c.drawString(40, height - 75, f"Tarih: {session.session_date}")

    headers = ["Ad Soyad", "Durum", "Not"]
    col_x = [40, 300, 420]
    y = height - 110
    c.setFont(font_name, 9)
    for idx, header in enumerate(headers):
        c.drawString(col_x[idx], y, header)
    y -= 16

    for enrollment in enrollments:
        if y < 80:
            c.showPage()
            c.setFont(font_name, 9)
            y = height - 60
            for idx, header in enumerate(headers):
                c.drawString(col_x[idx], y, header)
            y -= 16
        attendance = attendance_map.get(enrollment.student_id)
        status = status_labels.get(attendance.status, "â€”") if attendance else "â€”"
        note = attendance.note or "" if attendance else ""
        c.drawString(col_x[0], y, enrollment.student.full_name)
        c.drawString(col_x[1], y, status)
        c.drawString(col_x[2], y, note[:40])
        y -= 14

    c.save()
    buffer.seek(0)
    filename = f"attendance_session_{session.id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


@courses_bp.route("/<int:course_id>/attendance.csv")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def export_attendance(course_id):
    course = _course_query_for_user().filter_by(id=course_id).first_or_404()
    rows = []
    rows.append("Tarih,Ã–ÄŸrenci,Durum,Not")
    status_labels = {
        "present": "Mevcut",
        "absent": "Yok",
        "late": "GeÃ§ kaldÄ±",
        "excused": "Mazeretli"
    }
    for session in Session.query.filter_by(course_id=course.id, lesson_delivered=True).all():
        for attendance in Attendance.query.filter_by(session_id=session.id).all():
            status = status_labels.get(attendance.status, attendance.status or "")
            rows.append(f"{session.session_date},{attendance.student.full_name},{status},{attendance.note or ''}")
    csv_content = "\n".join(rows)
    return send_file(
        io.BytesIO(csv_content.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"attendance_course_{course.id}.csv"
    )



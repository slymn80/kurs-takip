import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from ...extensions import db
from sqlalchemy.exc import IntegrityError
from ...models import Organization, Location, CourseType, Teacher, User, Student, AuditLog
from ...models import Course, Enrollment, Attendance, PreRegistration, CourseLedgerEntry
from ...forms import OrganizationForm, LocationForm, CourseTypeForm, TeacherForm, StudentForm
from ...security import require_roles
from ...utils import serialize_json


definitions_bp = Blueprint("definitions", __name__)

ALLOWED_STUDENT_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}


def _allowed_student_image(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_STUDENT_IMAGE_EXTENSIONS


def _get_file_size(file_storage):
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    return size


def _save_student_upload(file_storage, upload_folder, max_bytes, label):
    if not file_storage or not file_storage.filename:
        return None, None
    filename = secure_filename(file_storage.filename)
    if not _allowed_student_image(filename):
        return None, f"{label} için sadece JPG veya PNG dosyası yükleyin."
    file_size = _get_file_size(file_storage)
    if file_size > max_bytes:
        max_kb = max_bytes // 1024
        return None, f"{label} en fazla {max_kb} KB olabilir."
    os.makedirs(upload_folder, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    file_storage.save(os.path.join(upload_folder, unique_name))
    return f"uploads/students/{unique_name}", None


@definitions_bp.route("/organizations", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def organizations():
    form = OrganizationForm()
    if form.validate_on_submit():
        org = Organization(
            name=form.name.data,
            responsible_person=form.responsible_person.data,
            phone=form.phone.data,
            email=form.email.data,
            address=form.address.data,
            notes=form.notes.data
        )
        db.session.add(org)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="organization", after_json=serialize_json({"name": org.name})))
        db.session.commit()
        flash("Kurum eklendi.", "success")
        return redirect(url_for("definitions.organizations"))
    items = Organization.query.order_by(Organization.name).all()
    return render_template("definitions/organizations.html", form=form, items=items)


@definitions_bp.route("/organizations/<int:org_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_organization(org_id):
    org = Organization.query.get_or_404(org_id)
    active_course = Course.query.filter_by(organization_id=org.id, status="active").first()
    if active_course:
        flash("Bu kurum aktif kurslarda kullanılıyor. Önce aktif kursları kaldırın.", "error")
        return redirect(url_for("definitions.organizations"))
    related_courses = Course.query.filter_by(organization_id=org.id).all()
    for course in related_courses:
        course.organization_name_cached = org.name
        course.organization_id = None
        db.session.add(course)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="delete",
        entity_type="organization",
        entity_id=org.id,
        after_json=serialize_json({"name": org.name})
    ))
    db.session.delete(org)
    db.session.commit()
    flash("Kurum silindi.", "success")
    return redirect(url_for("definitions.organizations"))


@definitions_bp.route("/organizations/<int:org_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def edit_organization(org_id):
    org = Organization.query.get_or_404(org_id)
    form = OrganizationForm(obj=org)
    if form.validate_on_submit():
        org.name = form.name.data
        org.responsible_person = form.responsible_person.data
        org.phone = form.phone.data
        org.email = form.email.data
        org.address = form.address.data
        org.notes = form.notes.data
        db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="organization", entity_id=org.id))
        db.session.commit()
        flash("Kurum güncellendi.", "success")
        return redirect(url_for("definitions.organizations"))
    return render_template("definitions/edit_organization.html", form=form, item=org)


@definitions_bp.route("/locations", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def locations():
    form = LocationForm()
    if form.validate_on_submit():
        loc = Location(
            name=form.name.data,
            address=form.address.data,
            capacity=form.capacity.data,
            has_smart_board=bool(form.has_smart_board.data),
            notes=form.notes.data
        )
        db.session.add(loc)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="location", after_json=serialize_json({"name": loc.name})))
        db.session.commit()
        flash("Yer eklendi.", "success")
        return redirect(url_for("definitions.locations"))
    items = Location.query.order_by(Location.name).all()
    return render_template("definitions/locations.html", form=form, items=items)


@definitions_bp.route("/locations/<int:loc_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_location(loc_id):
    loc = Location.query.get_or_404(loc_id)
    active_course = Course.query.filter_by(location_id=loc.id, status="active").first()
    if active_course:
        flash("Bu yer aktif kurslarda kullanılıyor. Önce aktif kursları kaldırın.", "error")
        return redirect(url_for("definitions.locations"))
    related_courses = Course.query.filter_by(location_id=loc.id).all()
    for course in related_courses:
        course.location_name_cached = loc.name
        course.location_id = None
        db.session.add(course)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="delete",
        entity_type="location",
        entity_id=loc.id,
        after_json=serialize_json({"name": loc.name})
    ))
    db.session.delete(loc)
    db.session.commit()
    flash("Yer silindi.", "success")
    return redirect(url_for("definitions.locations"))


@definitions_bp.route("/locations/<int:loc_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def edit_location(loc_id):
    loc = Location.query.get_or_404(loc_id)
    form = LocationForm(obj=loc)
    if form.validate_on_submit():
        loc.name = form.name.data
        loc.address = form.address.data
        loc.capacity = form.capacity.data
        loc.has_smart_board = bool(form.has_smart_board.data)
        loc.notes = form.notes.data
        db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="location", entity_id=loc.id))
        db.session.commit()
        flash("Yer güncellendi.", "success")
        return redirect(url_for("definitions.locations"))
    return render_template("definitions/edit_location.html", form=form, item=loc)


@definitions_bp.route("/course-types", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def course_types():
    form = CourseTypeForm()
    if form.validate_on_submit():
        ct = CourseType(
            name=form.name.data,
            course_hours=form.course_hours.data,
            delivery_mode=form.delivery_mode.data,
            description=form.description.data
        )
        db.session.add(ct)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="course_type", after_json=serialize_json({"name": ct.name})))
        db.session.commit()
        flash("Kurs tipi eklendi.", "success")
        return redirect(url_for("definitions.course_types"))
    items = CourseType.query.order_by(CourseType.name).all()
    return render_template("definitions/course_types.html", form=form, items=items)


@definitions_bp.route("/course-types/<int:ct_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_course_type(ct_id):
    ct = CourseType.query.get_or_404(ct_id)
    active_course = Course.query.filter_by(course_type_id=ct.id, status="active").first()
    if active_course:
        flash("Bu kurs tipi aktif kurslarda kullanılıyor. Önce aktif kursları kaldırın.", "error")
        return redirect(url_for("definitions.course_types"))
    related_courses = Course.query.filter_by(course_type_id=ct.id).all()
    for course in related_courses:
        course.course_type_name_cached = ct.name
        course.course_type_id = None
        db.session.add(course)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="delete",
        entity_type="course_type",
        entity_id=ct.id,
        after_json=serialize_json({"name": ct.name})
    ))
    db.session.delete(ct)
    db.session.commit()
    flash("Kurs tipi silindi.", "success")
    return redirect(url_for("definitions.course_types"))


@definitions_bp.route("/course-types/<int:ct_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def edit_course_type(ct_id):
    ct = CourseType.query.get_or_404(ct_id)
    form = CourseTypeForm(obj=ct)
    if form.validate_on_submit():
        ct.name = form.name.data
        ct.course_hours = form.course_hours.data
        ct.delivery_mode = form.delivery_mode.data
        ct.description = form.description.data
        db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="course_type", entity_id=ct.id))
        db.session.commit()
        flash("Kurs tipi güncellendi.", "success")
        return redirect(url_for("definitions.course_types"))
    return render_template("definitions/edit_course_type.html", form=form, item=ct)


@definitions_bp.route("/teachers", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def teachers():
    form = TeacherForm()
    teacher_users = User.query.filter_by(role="teacher").order_by(User.full_name).all()
    linked_user_ids = {t.user_id for t in Teacher.query.filter(Teacher.user_id.isnot(None)).all()}
    available_users = [u for u in teacher_users if u.id not in linked_user_ids]
    form.user_id.choices = [(0, "Seçilmedi")] + [(u.id, f"{u.full_name} ({u.username})") for u in available_users]
    if form.validate_on_submit():
        selected_user = User.query.get(form.user_id.data) if form.user_id.data else None
        if not selected_user:
            flash("Lütfen öğretmen rolündeki kullanıcıyı seçin.", "error")
            return redirect(url_for("definitions.teachers"))
        if Teacher.query.filter_by(user_id=selected_user.id).first():
            flash("Bu kullanıcı için öğretmen profili zaten oluşturulmuş.", "error")
            return redirect(url_for("definitions.teachers"))
        identity_number = (form.identity_number.data or "").strip() or selected_user.identity_number
        if not identity_number:
            flash("T.C./IIN bilgisi zorunludur.", "error")
            return redirect(url_for("definitions.teachers"))
        if identity_number:
            existing_teacher = Teacher.query.filter_by(identity_number=identity_number).first()
            if existing_teacher:
                flash("Bu T.C./IIN ile kayıtlı bir öğretmen zaten var.", "error")
                return redirect(url_for("definitions.teachers"))
        phone_value = (form.phone.data or "").strip() or (selected_user.phone or "")
        email_value = (form.email.data or "").strip() or (selected_user.email or "")
        if not phone_value or not email_value:
            flash("Telefon ve e-posta bilgisi zorunludur.", "error")
            return redirect(url_for("definitions.teachers"))
        teacher = Teacher(
            user_id=selected_user.id,
            full_name=selected_user.full_name,
            identity_number=identity_number,
            title=form.title.data,
            branch=form.branch.data,
            phone=phone_value,
            email=email_value,
            notes=form.notes.data
        )
        db.session.add(teacher)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="teacher", after_json=serialize_json({"user_id": teacher.user_id})))
        db.session.commit()
        flash("Öğretmen profili eklendi.", "success")
        return redirect(url_for("definitions.teachers"))
    items = Teacher.query.all()
    return render_template(
        "definitions/teachers.html",
        form=form,
        items=items,
        available_users=available_users,
        selected_user_id=form.user_id.data or 0
    )


@definitions_bp.route("/teachers/<int:teacher_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    active_course = Course.query.filter_by(teacher_id=teacher.id, status="active").first()
    if active_course:
        flash("Bu öğretmen aktif kurslara atanmış. Önce aktif kurslardan öğretmeni kaldırın.", "error")
        return redirect(url_for("definitions.teachers"))

    affected_courses = Course.query.filter_by(teacher_id=teacher.id).all()
    for course in affected_courses:
        course.teacher_name_cached = teacher.full_name
        course.teacher_id = None
        course.teacher_user_id = None
        db.session.add(course)
    db.session.delete(teacher)
    db.session.commit()
    flash("Öğretmen profili silindi.", "success")
    return redirect(url_for("definitions.teachers"))


@definitions_bp.route("/teachers/<int:teacher_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def edit_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    form = TeacherForm(obj=teacher)
    teacher_users = User.query.filter_by(role="teacher").order_by(User.full_name).all()
    linked_user_ids = {t.user_id for t in Teacher.query.filter(Teacher.user_id.isnot(None), Teacher.id != teacher.id).all()}
    available_users = [u for u in teacher_users if u.id not in linked_user_ids]
    form.user_id.choices = [(0, "Seçilmedi")] + [(u.id, f"{u.full_name} ({u.username})") for u in available_users]
    form.user_id.data = teacher.user_id or 0
    if form.validate_on_submit():
        selected_user = User.query.get(form.user_id.data) if form.user_id.data else None
        if selected_user:
            teacher.user_id = selected_user.id
            teacher.full_name = selected_user.full_name
        elif not form.full_name.data:
            flash("Ad soyad boş olamaz.", "error")
            return render_template("definitions/edit_teacher.html", form=form, item=teacher)
        identity_number = (form.identity_number.data or "").strip() or (selected_user.identity_number if selected_user else None)
        if not identity_number:
            flash("T.C./IIN bilgisi zorunludur.", "error")
            return render_template("definitions/edit_teacher.html", form=form, item=teacher)
        if identity_number:
            existing_teacher = Teacher.query.filter_by(identity_number=identity_number).first()
            if existing_teacher and existing_teacher.id != teacher.id:
                flash("Bu T.C./IIN ile kayıtlı başka bir öğretmen var.", "error")
                return render_template("definitions/edit_teacher.html", form=form, item=teacher)
        teacher.identity_number = identity_number
        teacher.title = form.title.data
        teacher.branch = form.branch.data
        phone_value = (form.phone.data or "").strip() or (selected_user.phone if selected_user else teacher.phone)
        email_value = (form.email.data or "").strip() or (selected_user.email if selected_user else teacher.email)
        if not phone_value or not email_value:
            flash("Telefon ve e-posta bilgisi zorunludur.", "error")
            return render_template("definitions/edit_teacher.html", form=form, item=teacher)
        teacher.phone = phone_value
        teacher.email = email_value
        teacher.notes = form.notes.data
        db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="teacher", entity_id=teacher.id))
        db.session.commit()
        flash("Öğretmen profili güncellendi.", "success")
        return redirect(url_for("definitions.teachers"))
    return render_template(
        "definitions/edit_teacher.html",
        form=form,
        item=teacher,
        available_users=available_users,
        selected_user_id=form.user_id.data or 0
    )


@definitions_bp.route("/students", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def students():
    form = StudentForm()
    if current_user.role == "teacher":
        courses_query = Course.query.filter(Course.teacher_user_id == current_user.id)
    else:
        courses_query = Course.query
    form.course_id.choices = [(0, "Se\u00e7ilmedi")] + [
        (c.id, c.title) for c in courses_query.order_by(Course.created_at.desc()).all()
    ]
    max_file_kb = current_app.config["STUDENT_UPLOAD_MAX_BYTES"] // 1024
    if form.validate_on_submit():
        existing_student = Student.query.filter_by(iin=form.iin.data).first()
        if existing_student:
            flash("Bu IIN/TC ile kayıtlı bir kursiyer zaten var.", "error")
            items = Student.query.filter(Student.is_active == True).order_by(Student.created_at.desc()).all()
            return render_template("definitions/students.html", form=form, items=items, max_file_kb=max_file_kb)
        upload_folder = current_app.config["STUDENT_UPLOAD_FOLDER"]
        max_bytes = current_app.config["STUDENT_UPLOAD_MAX_BYTES"]
        photo_path, photo_error = _save_student_upload(
            request.files.get("photo"),
            upload_folder,
            max_bytes,
            "Öğrenci fotoğrafı"
        )
        id_path, id_error = _save_student_upload(
            request.files.get("id_image"),
            upload_folder,
            max_bytes,
            "Kimlik görseli"
        )
        errors = [err for err in [photo_error, id_error] if err]
        if errors:
            for err in errors:
                flash(err, "error")
            items = Student.query.filter(Student.is_active == True).order_by(Student.created_at.desc()).all()
            return render_template("definitions/students.html", form=form, items=items, max_file_kb=max_file_kb)
        student = Student(
            full_name=form.full_name.data,
            iin=form.iin.data,
            education_level=form.education_level.data,
            phone=form.phone.data,
            email=form.email.data,
            photo_path=photo_path,
            id_image_path=id_path,
            notes=form.notes.data
        )
        db.session.add(student)
        db.session.flush()
        if form.course_id.data:
            db.session.add(Enrollment(course_id=form.course_id.data, student_id=student.id))
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="student", after_json=serialize_json({"name": student.full_name})))
        db.session.commit()
        flash("Kursiyer eklendi.", "success")
        return redirect(url_for("definitions.students"))
    items = Student.query.filter(Student.is_active == True).order_by(Student.created_at.desc()).all()
    return render_template("definitions/students.html", form=form, items=items, max_file_kb=max_file_kb)


@definitions_bp.route("/students/<int:student_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    Enrollment.query.filter_by(student_id=student.id).update(
        {Enrollment.student_id: None},
        synchronize_session=False
    )
    Attendance.query.filter_by(student_id=student.id).update(
        {Attendance.student_id: None},
        synchronize_session=False
    )
    PreRegistration.query.filter_by(student_id=student.id).update(
        {PreRegistration.student_id: None},
        synchronize_session=False
    )
    CourseLedgerEntry.query.filter_by(student_id=student.id).update(
        {CourseLedgerEntry.student_id: None},
        synchronize_session=False
    )
    db.session.delete(student)
    try:
        db.session.commit()
        flash("Kursiyer silindi. Geçmiş kayıtlar korunmuştur.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Kursiyer silinemedi. İlişkili kayıtlar var.", "error")
    return redirect(url_for("definitions.students"))


@definitions_bp.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("coordinator", "principal", "attache", "admin")
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    form = StudentForm(obj=student)
    if current_user.role == "teacher":
        courses_query = Course.query.filter(Course.teacher_user_id == current_user.id)
    else:
        courses_query = Course.query
    form.course_id.choices = [(0, "Se\u00e7ilmedi")] + [
        (c.id, c.title) for c in courses_query.order_by(Course.created_at.desc()).all()
    ]
    max_file_kb = current_app.config["STUDENT_UPLOAD_MAX_BYTES"] // 1024
    if form.validate_on_submit():
        existing_student = Student.query.filter_by(iin=form.iin.data).first()
        if existing_student and existing_student.id != student.id:
            flash("Bu IIN/TC ile kayıtlı başka bir kursiyer var.", "error")
            return render_template("definitions/edit_student.html", form=form, item=student, max_file_kb=max_file_kb)
        upload_folder = current_app.config["STUDENT_UPLOAD_FOLDER"]
        max_bytes = current_app.config["STUDENT_UPLOAD_MAX_BYTES"]
        photo_path, photo_error = _save_student_upload(
            request.files.get("photo"),
            upload_folder,
            max_bytes,
            "Öğrenci fotoğrafı"
        )
        id_path, id_error = _save_student_upload(
            request.files.get("id_image"),
            upload_folder,
            max_bytes,
            "Kimlik görseli"
        )
        errors = [err for err in [photo_error, id_error] if err]
        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("definitions/edit_student.html", form=form, item=student, max_file_kb=max_file_kb)
        student.full_name = form.full_name.data
        student.iin = form.iin.data
        student.education_level = form.education_level.data
        student.phone = form.phone.data
        student.email = form.email.data
        if photo_path:
            student.photo_path = photo_path
        if id_path:
            student.id_image_path = id_path
        student.notes = form.notes.data
        db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="student", entity_id=student.id))
        db.session.commit()
        flash("Kursiyer güncellendi.", "success")
        return redirect(url_for("definitions.students"))
    return render_template("definitions/edit_student.html", form=form, item=student, max_file_kb=max_file_kb)




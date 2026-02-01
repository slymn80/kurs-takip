import io
import os
from datetime import datetime
from flask import Blueprint, render_template, send_file, request
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from openpyxl import Workbook
from ...models import Course, Enrollment, Student, Teacher, Organization
from ...security import require_roles


reports_bp = Blueprint("reports", __name__)


def _font_name():
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


def _build_report(report_type, filters=None):
    filters = filters or {}
    restrict_course_ids = None
    if current_user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        query = Course.query
        if teacher:
            query = query.filter(Course.teacher_id == teacher.id)
        else:
            query = query.filter(Course.teacher_user_id == current_user.id)
        restrict_course_ids = [c.id for c in query.all()]

    if report_type == "courses":
        status = filters.get("course_status")
        query = Course.query
        if restrict_course_ids is not None:
            query = query.filter(Course.id.in_(restrict_course_ids))
        if status:
            query = query.filter(Course.status == status)
        rows = []
        for c in query.order_by(Course.created_at.desc()).all():
            rows.append([c.id, c.title, c.status, str(c.start_date), str(c.end_date), c.teacher.full_name if c.teacher else "-"])
        return "Kurs Listesi", ["ID", "Kurs", "Durum", "Başlangıç", "Bitiş", "Öğretmen"], rows

    if report_type == "course_students":
        course_id = filters.get("course_id")
        query = Enrollment.query.join(Course).join(Student)
        if restrict_course_ids is not None:
            query = query.filter(Enrollment.course_id.in_(restrict_course_ids))
        if course_id:
            query = query.filter(Enrollment.course_id == course_id)
        rows = []
        for e in query.order_by(Course.title).all():
            rows.append([e.course.title, e.student.full_name, e.student.iin, e.student.phone or "-"])
        return "Kurs Bazında Öğrenci Listesi", ["Kurs", "Öğrenci", "IIN", "Telefon"], rows

    if report_type == "teachers":
        branch = filters.get("branch")
        query = Teacher.query
        if current_user.role == "teacher":
            query = query.filter(Teacher.user_id == current_user.id)
        if branch:
            query = query.filter(Teacher.branch == branch)
        rows = []
        for t in query.order_by(Teacher.full_name).all():
            rows.append([t.full_name, t.title, t.branch, t.phone, t.email])
        return "Öğretmen Listesi", ["Ad", "Unvan", "Branş", "Telefon", "E-posta"], rows

    if report_type == "organizations":
        org_id = filters.get("organization_id")
        query = Organization.query
        if restrict_course_ids is not None:
            query = query.join(Course, Course.organization_id == Organization.id).filter(Course.id.in_(restrict_course_ids))
        if org_id:
            query = query.filter(Organization.id == org_id)
        rows = []
        for o in query.order_by(Organization.name).all():
            rows.append([o.name, o.responsible_person, o.phone, o.email])
        return "Kurum Listesi", ["Kurum", "Sorumlu", "Telefon", "E-posta"], rows

    if report_type == "ended_courses":
        teacher_id = filters.get("teacher_id")
        query = Course.query.filter(Course.status == "ended")
        if restrict_course_ids is not None:
            query = query.filter(Course.id.in_(restrict_course_ids))
        if teacher_id:
            query = query.filter(Course.teacher_id == teacher_id)
        rows = []
        for c in query.order_by(Course.created_at.desc()).all():
            rows.append([c.id, c.title, str(c.start_date), str(c.end_date), c.teacher.full_name if c.teacher else "-"])
        return "Biten Kurslar", ["ID", "Kurs", "Başlangıç", "Bitiş", "Öğretmen"], rows

    if report_type == "dropped_courses":
        teacher_id = filters.get("teacher_id")
        query = Course.query.filter(Course.status == "dropped")
        if restrict_course_ids is not None:
            query = query.filter(Course.id.in_(restrict_course_ids))
        if teacher_id:
            query = query.filter(Course.teacher_id == teacher_id)
        rows = []
        for c in query.order_by(Course.created_at.desc()).all():
            rows.append([c.id, c.title, str(c.start_date), str(c.end_date), c.teacher.full_name if c.teacher else "-"])
        return "Yarım Kalan Kurslar", ["ID", "Kurs", "Başlangıç", "Bitiş", "Öğretmen"], rows

    if report_type == "teacher_courses":
        teacher_id = filters.get("teacher_id")
        rows = []
        if teacher_id:
            for c in Course.query.filter(Course.teacher_id == teacher_id).order_by(Course.created_at.desc()).all():
                rows.append([c.title, c.status, str(c.start_date), str(c.end_date)])
            return "Öğretmene Atanan Kurslar", ["Kurs", "Durum", "Başlangıç", "Bitiş"], rows

        query = Course.query
        if restrict_course_ids is not None:
            query = query.filter(Course.id.in_(restrict_course_ids))
        for c in query.order_by(Course.created_at.desc()).all():
            rows.append([c.teacher.full_name if c.teacher else "-", c.title, c.status, str(c.start_date), str(c.end_date)])
        return "Tüm Öğretmenlerin Kursları", ["Öğretmen", "Kurs", "Durum", "Başlangıç", "Bitiş"], rows

    return None, None, None


def _pdf_report(title, headers, rows):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = _font_name()
    local_stamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    page_num = 1

    def draw_footer(page_number):
        c.setFont(font_name, 8)
        c.drawString(40, 20, f"{local_stamp}")
        c.drawRightString(width - 40, 20, f"Sayfa {page_number}")

    def finish_page():
        nonlocal page_num
        draw_footer(page_num)
        c.showPage()
        page_num += 1

    def draw_signature_block():
        sig_y = 70
        c.setFont(font_name, 9)
        c.line(60, sig_y, 200, sig_y)
        c.line(width - 200, sig_y, width - 60, sig_y)
        c.drawString(60, sig_y - 12, "Öğretmen")
        right_center = width - 130
        c.drawCentredString(right_center, sig_y - 12, "Eğitim Ataşesi")

    c.setFont(font_name, 14)
    c.drawString(40, height - 40, title)
    c.setFont(font_name, 9)

    y = height - 70
    col_width = max(80, int((width - 80) / max(1, len(headers))))

    def draw_row(values, y_pos, bold=False):
        if bold:
            c.setFont(font_name, 9)
        x = 40
        for val in values:
            text = str(val) if val is not None else ""
            c.drawString(x, y_pos, text[:30])
            x += col_width

    draw_row(headers, y, bold=True)
    y -= 18

    for row in rows:
        if y < 90:
            finish_page()
            c.setFont(font_name, 9)
            y = height - 60
            draw_row(headers, y, bold=True)
            y -= 18
        draw_row(row, y)
        y -= 14

    if y < 110:
        finish_page()
        c.setFont(font_name, 9)
        y = height - 60

    draw_signature_block()
    draw_footer(page_num)
    c.save()
    buffer.seek(0)
    return buffer


def _xlsx_report(headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.orientation = ws.ORIENTATION_PORTRAIT
    ws.page_margins.left = 0.5
    ws.page_margins.right = 0.5
    ws.page_margins.top = 0.6
    ws.page_margins.bottom = 0.8
    ws.oddFooter.left.text = "&D &T"
    ws.oddFooter.right.text = "Sayfa &P"

    ws.append(headers)
    for row in rows:
        ws.append(row)

    ws.append([])
    ws.append(["Öğretmen"])
    ws.append(["", "", "", "Eğitim Ataşesi"])

    from openpyxl.styles import Alignment
    name_row = ws.max_row - 0
    if ws.max_column >= 4:
        ws.merge_cells(start_row=name_row, start_column=4, end_row=name_row, end_column=ws.max_column)
        ws.cell(row=name_row, column=4).alignment = Alignment(horizontal="center")

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


@reports_bp.route("/")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def index():
    teacher_id = request.args.get("teacher_id", type=int)
    course_status = request.args.get("course_status")
    course_id = request.args.get("course_id", type=int)
    branch = request.args.get("branch")
    organization_id = request.args.get("organization_id", type=int)
    ended_teacher_id = request.args.get("ended_teacher_id", type=int)
    dropped_teacher_id = request.args.get("dropped_teacher_id", type=int)

    courses_query = Course.query
    if current_user.role == "teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        if teacher:
            teacher_id = teacher.id
            courses_query = courses_query.filter(Course.teacher_id == teacher.id)
        else:
            courses_query = courses_query.filter(Course.teacher_user_id == current_user.id)
    if course_status:
        courses_query = courses_query.filter(Course.status == course_status)
    courses = courses_query.order_by(Course.created_at.desc()).all()

    course_students_query = Enrollment.query.join(Course).join(Student)
    if current_user.role == "teacher":
        course_students_query = course_students_query.filter(Course.id.in_([c.id for c in courses_query.all()]))
    if course_id:
        course_students_query = course_students_query.filter(Enrollment.course_id == course_id)
    course_students = course_students_query.order_by(Course.title).all()

    teachers_query = Teacher.query
    if current_user.role == "teacher":
        teachers_query = teachers_query.filter(Teacher.user_id == current_user.id)
    if branch:
        teachers_query = teachers_query.filter(Teacher.branch == branch)
    teachers = teachers_query.order_by(Teacher.full_name).all()

    organizations_query = Organization.query
    if current_user.role == "teacher":
        organizations_query = organizations_query.join(Course, Course.organization_id == Organization.id).filter(Course.id.in_([c.id for c in courses_query.all()]))
    if organization_id:
        organizations_query = organizations_query.filter(Organization.id == organization_id)
    organizations = organizations_query.order_by(Organization.name).all()

    ended_query = Course.query.filter(Course.status == "ended")
    if current_user.role == "teacher":
        ended_query = ended_query.filter(Course.id.in_([c.id for c in courses_query.all()]))
    if ended_teacher_id:
        ended_query = ended_query.filter(Course.teacher_id == ended_teacher_id)
    ended_courses = ended_query.order_by(Course.created_at.desc()).all()

    dropped_query = Course.query.filter(Course.status == "dropped")
    if current_user.role == "teacher":
        dropped_query = dropped_query.filter(Course.id.in_([c.id for c in courses_query.all()]))
    if dropped_teacher_id:
        dropped_query = dropped_query.filter(Course.teacher_id == dropped_teacher_id)
    dropped_courses = dropped_query.order_by(Course.created_at.desc()).all()

    teacher_courses = []
    if teacher_id:
        teacher_courses = Course.query.filter(Course.teacher_id == teacher_id).order_by(Course.created_at.desc()).all()
    else:
        if current_user.role == "teacher":
            teacher_courses = courses_query.order_by(Course.created_at.desc()).all()
        else:
            teacher_courses = Course.query.order_by(Course.created_at.desc()).all()

    all_courses = courses_query.order_by(Course.title).all()
    if current_user.role == "teacher":
        all_teachers = Teacher.query.filter_by(user_id=current_user.id).order_by(Teacher.full_name).all()
    else:
        all_teachers = Teacher.query.order_by(Teacher.full_name).all()

    return render_template(
        "reports/index.html",
        courses=courses,
        course_students=course_students,
        teachers=teachers,
        organizations=organizations,
        ended_courses=ended_courses,
        dropped_courses=dropped_courses,
        teacher_courses=teacher_courses,
        selected_teacher_id=teacher_id or "",
        selected_course_status=course_status or "",
        selected_course_id=course_id or "",
        selected_branch=branch or "",
        selected_organization_id=organization_id or "",
        selected_ended_teacher_id=ended_teacher_id or "",
        selected_dropped_teacher_id=dropped_teacher_id or "",
        all_courses=all_courses,
        all_teachers=all_teachers
    )


@reports_bp.route("/download/<report_type>")
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def download(report_type):
    fmt = request.args.get("format", "pdf")
    filters = {
        "teacher_id": request.args.get("teacher_id", type=int),
        "course_status": request.args.get("course_status"),
        "course_id": request.args.get("course_id", type=int),
        "branch": request.args.get("branch"),
        "organization_id": request.args.get("organization_id", type=int)
    }
    title, headers, rows = _build_report(report_type, filters=filters)
    if not title:
        return "Not found", 404

    filename = f"{report_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.{fmt}"

    if fmt == "xlsx":
        stream = _xlsx_report(headers, rows)
        return send_file(stream, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    stream = _pdf_report(title, headers, rows)
    return send_file(stream, as_attachment=True, download_name=filename, mimetype="application/pdf")

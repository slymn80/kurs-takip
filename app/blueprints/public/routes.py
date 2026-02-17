import os
import uuid
from flask import Blueprint, render_template, request, flash, current_app, redirect, url_for
from ...extensions import db
from ...models import Student, Enrollment, Course, PreRegistration
from ...forms import PreRegistrationForm


public_bp = Blueprint("public", __name__)

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


def _save_student_upload(file_storage, upload_folder, max_bytes, label, t):
    if not file_storage or not file_storage.filename:
        return None, None
    filename = file_storage.filename
    if not _allowed_student_image(filename):
        return None, t["file_type"].format(label=label)
    file_size = _get_file_size(file_storage)
    if file_size > max_bytes:
        max_kb = max_bytes // 1024
        return None, t["file_size"].format(label=label, max_kb=max_kb)
    os.makedirs(upload_folder, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    file_storage.save(os.path.join(upload_folder, unique_name))
    return f"uploads/students/{unique_name}", None


def _translations(lang):
    tr = {
        "title": "Kursiyer Ön Kayıt",
        "subtitle": "Lütfen tüm alanları eksiksiz doldurun.",
        "full_name": "Ad Soyad",
        "iin": "IIN/TC",
        "education": "Eğitim Durumu",
        "course_level": "Kurs Seviyesi",
        "phone": "Telefon",
        "email": "E-posta",
        "photo": "Öğrenci Fotoğrafı",
        "id_image": "Kimlik Görseli",
        "notes": "Not",
        "submit": "Ön Kayıt Gönder",
        "back": "Giriş sayfasına dön",
        "photo_hint": "JPG/PNG, en fazla {max_kb} KB.",
        "pending": "Bu IIN için bekleyen bir ön kayıt var.",
        "active": "Bu IIN ile aktif bir kayıt bulundu. Ön kayıt oluşturulamaz.",
        "success": "Ön kayıt alındı. Başvurunuz değerlendirilecektir.",
        "file_type": "{label} için sadece JPG veya PNG dosyası yükleyin.",
        "file_size": "{label} en fazla {max_kb} KB olabilir."
    }
    kz = {
        "title": "Тіркелушінің алдын ала тіркелуі",
        "subtitle": "Барлық жолдарды толық толтырыңыз.",
        "full_name": "Аты-жөні",
        "iin": "ЖСН",
        "education": "Білім деңгейі",
        "course_level": "Курс деңгейі",
        "phone": "Телефон",
        "email": "Эл. пошта",
        "photo": "Оқушының фотосы",
        "id_image": "Жеке куәлік суреті",
        "notes": "Ескертпе",
        "submit": "Алдын ала тіркелу жіберу",
        "back": "Кіру бетіне оралу",
        "photo_hint": "JPG/PNG, ең көбі {max_kb} KB.",
        "pending": "Бұл ЖСН бойынша алдын ала өтінім бар.",
        "active": "Бұл ЖСН бойынша белсенді тіркеу бар. Алдын ала тіркелу мүмкін емес.",
        "success": "Алдын ала тіркелу қабылданды. Өтінішіңіз қаралады.",
        "file_type": "{label} үшін тек JPG немесе PNG файлын жүктеңіз.",
        "file_size": "{label} ең көбі {max_kb} KB болуы керек."
    }
    en = {
        "title": "Pre-registration",
        "subtitle": "Please fill in all fields completely.",
        "full_name": "Full name",
        "iin": "National ID",
        "education": "Education level",
        "course_level": "Course level",
        "phone": "Phone",
        "email": "Email",
        "photo": "Student photo",
        "id_image": "ID image",
        "notes": "Notes",
        "submit": "Submit pre-registration",
        "back": "Back to login",
        "photo_hint": "JPG/PNG, max {max_kb} KB.",
        "pending": "A pending pre-registration exists for this ID.",
        "active": "An active enrollment exists for this ID. Pre-registration not allowed.",
        "success": "Pre-registration submitted. Your application will be reviewed.",
        "file_type": "Only JPG or PNG files are allowed for {label}.",
        "file_size": "{label} can be at most {max_kb} KB."
    }
    ru = {
        "title": "Предварительная регистрация",
        "subtitle": "Пожалуйста, заполните все поля полностью.",
        "full_name": "ФИО",
        "iin": "ИИН",
        "education": "Уровень образования",
        "course_level": "Уровень курса",
        "phone": "Телефон",
        "email": "Email",
        "photo": "Фото студента",
        "id_image": "Изображение удостоверения",
        "notes": "Примечание",
        "submit": "Отправить предварительную регистрацию",
        "back": "Вернуться к входу",
        "photo_hint": "JPG/PNG, максимум {max_kb} KB.",
        "pending": "По этому ИИН уже есть ожидающая заявка.",
        "active": "По этому ИИН есть активная регистрация. Предрегистрация невозможна.",
        "success": "Предрегистрация отправлена. Заявка будет рассмотрена.",
        "file_type": "Для {label} разрешены только JPG или PNG файлы.",
        "file_size": "{label} может быть не более {max_kb} KB."
    }
    return {"tr": tr, "kz": kz, "en": en, "ru": ru}.get(lang, tr)


def _education_choices(lang):
    if lang == "kz":
        return [
            ("primary", "Бастауыш"),
            ("middle", "Орта"),
            ("high", "Жоғары сынып"),
            ("university", "Университет"),
            ("other", "Басқа")
        ]
    if lang == "en":
        return [
            ("primary", "Primary"),
            ("middle", "Middle"),
            ("high", "High school"),
            ("university", "University"),
            ("other", "Other")
        ]
    if lang == "ru":
        return [
            ("primary", "Начальная"),
            ("middle", "Средняя"),
            ("high", "Старшая"),
            ("university", "Университет"),
            ("other", "Другое")
        ]
    return [
        ("primary", "İlkokul"),
        ("middle", "Ortaokul"),
        ("high", "Lise"),
        ("university", "Üniversite"),
        ("other", "Diğer")
    ]


def _course_level_choices(lang):
    label = {
        "tr": "Seviye",
        "kz": "Деңгей",
        "en": "Level",
        "ru": "Уровень"
    }.get(lang, "Seviye")
    return [("A1", "A1"), ("A2", "A2"), ("B1", "B1"), ("B2", "B2"), ("C1", "C1")]


@public_bp.route("/pre-registration", methods=["GET", "POST"])
def pre_registration():
    lang = (request.args.get("lang") or "tr").lower()
    if lang not in {"tr", "kz", "en", "ru"}:
        lang = "tr"
    t = _translations(lang)
    form = PreRegistrationForm()
    form.education_level.choices = _education_choices(lang)
    form.course_level.choices = _course_level_choices(lang)
    max_file_kb = current_app.config["STUDENT_UPLOAD_MAX_BYTES"] // 1024
    if form.validate_on_submit():
        iin_value = form.iin.data.strip()
        existing_student = Student.query.filter_by(iin=iin_value).first()

        pending_exists = PreRegistration.query.filter_by(iin=iin_value, status="pending").first()
        if pending_exists:
            flash(t["pending"], "error")
            return render_template("public/pre_registration.html", form=form, max_file_kb=max_file_kb, t=t, lang=lang)

        if existing_student:
            active_enrollment = Enrollment.query.join(Course).filter(
                Enrollment.student_id == existing_student.id,
                Enrollment.status == "active",
                Course.status == "active"
            ).first()
            if active_enrollment:
                flash(t["active"], "error")
                return render_template("public/pre_registration.html", form=form, max_file_kb=max_file_kb, t=t, lang=lang)

        prereg = PreRegistration(
            student_id=existing_student.id if existing_student else None,
            full_name=form.full_name.data,
            iin=iin_value,
            education_level=form.education_level.data,
            course_level=form.course_level.data,
            phone=form.phone.data,
            email=form.email.data,
            notes=form.notes.data,
            status="pending"
        )
        db.session.add(prereg)
        db.session.commit()
        flash(t["success"], "success")
        return redirect(url_for("auth.login"))
    return render_template("public/pre_registration.html", form=form, max_file_kb=max_file_kb, t=t, lang=lang)

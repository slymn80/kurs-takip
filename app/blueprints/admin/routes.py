import io
import json
import os
import threading
from datetime import datetime, time, timedelta
from sqlalchemy import func
import secrets
import string
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app, send_file, jsonify
from sqlalchemy.exc import IntegrityError
from flask_login import login_required, current_user
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from ...extensions import db, bcrypt
from ...models import (
    User,
    SystemSetting,
    PlacementPromptHistory,
    AuditLog,
    Course,
    Enrollment,
    Teacher,
    Student,
    Organization,
    Attendance,
    Message,
    Announcement,
    Certificate,
    CourseLedgerEntry,
    ApiToken,
    PlacementQuestion,
    PreRegistration,
    PlacementTestQuestion,
    PlacementAnswer,
    PlacementTest,
    PlacementCandidate,
    Session
)
from ...forms import UserForm
from ...security import require_roles, hash_api_token
from ...utils import serialize_json
from ...services.notifications import emit_webhook
from ...services.placement import create_question_group


admin_bp = Blueprint("admin", __name__)
generation_status = None

DEFAULT_LOGIN_ASSISTANT_PROMPT = (
    "Sen Almatı Eğitim Ataşeliği Kurs Takip Otomasyonu için YZ 7/24 asistansın.\n"
    "Sadece aşağıdaki tek bilgi kaynağına dayanarak cevap ver. Bilgi uydurma.\n"
    "Desteklenen diller: tr, kz, ru, en. Seçilen dilde yanıt ver.\n"
    "Kapsam: Türkçe kurslar, ön kayıt, seviye sınavı, kurs süreçleri, iletişim ve genel yönlendirme.\n"
    "Kişisel veri güvenliği: telefon, e-posta, T.C./IIN gibi hassas bilgileri paylaşma.\n"
    "Bilgi kaynağında olmayan bir konuda net şekilde 'Bu konuda güncel/ek bilgi yok' de.\n\n"
    "Yeni açılan/açılacak kurslar (kaynak: turkce_kurs_listesi.xlsx):\n"
    "- TR-A1-101 | Talgar Dil Akademisi | Günlük Türkçe Başlangıç | A1 | Pazartesi-Çarşamba | 18:30–20:00 | 10 Mart 2026 | 48 Saat | Elif Kaya | Yüz Yüze\n"
    "- TR-A2-204 | Astana Language Hub | Konuşma Odaklı Türkçe | A2 | Salı-Perşembe | 19:00–20:30 | 12 Mart 2026 | 60 Saat | Mehmet Arslan | Online\n"
    "- TR-B1-315 | Orta Asya Eğitim Merkezi | Akademik Türkçe | B1 | Cumartesi | 10:00–13:00 | 15 Mart 2026 | 36 Saat | Aigerim N. | Hibrit\n"
    "- TR-B2-402 | Global Edu Center | İş Türkçesi | B2 | Pazartesi | 20:00–22:00 | 17 Mart 2026 | 40 Saat | Serkan Demir | Online\n"
    "- TR-C1-550 | Türkçe Kültür Enstitüsü | İleri Seviye Tartışma | C1 | Pazar | 11:00–14:00 | 22 Mart 2026 | 30 Saat | Zeynep Yılmaz | Yüz Yüze\n"
    "- TR-A1-118 | Steppe Language School | Hızlandırılmış Türkçe | A1 | Pazartesi-Salı-Çarşamba | 09:00–11:00 | 25 Mart 2026 | 72 Saat | Daniyar K. | Yüz Yüze\n"
    "- TR-B1-377 | Nova Education | Üniversite Hazırlık Türkçesi | B1 | Cuma | 18:00–21:00 | 28 Mart 2026 | 45 Saat | Nazlı Çetin | Online\n"
    "- TR-A2-290 | SilkRoad Language Center | Günlük Diyalog Atölyesi | A2 | Çarşamba-Cuma | 17:30–19:00 | 30 Mart 2026 | 32 Saat | Murat Akın | Hibrit\n"
    "- TR-C1-600 | Eurasia Academy | Akademik Yazım Türkçesi | C1 | Cumartesi-Pazar | 14:00–16:00 | 5 Nisan 2026 | 50 Saat | Prof. Deniz Ö. | Online\n"
)

def _pdf_font_name():
    candidates = [
        ("Arial", r"C:\Windows\Fonts\arial.ttf"),
        ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("NotoSans", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name
            except Exception:
                continue
    return "Helvetica"

def _generate_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%?"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _set_generation_status(state, message, group_name=None):
    payload = {
        "state": state,
        "message": message,
        "group_name": group_name,
        "updated_at": datetime.utcnow().isoformat()
    }
    setting = SystemSetting.query.filter_by(key="placement_generation_status").first()
    if not setting:
        setting = SystemSetting(key="placement_generation_status", value=json.dumps(payload, ensure_ascii=False))
        db.session.add(setting)
    else:
        setting.value = json.dumps(payload, ensure_ascii=False)
    db.session.commit()


def _run_generation(app, count, set_active):
    with app.app_context():
        try:
            _set_generation_status("running", "Soru üretimi başladı.", None)
            group_name = create_question_group(count=count)
            if set_active:
                setting = SystemSetting.query.filter_by(key="placement_active_group").first()
                if not setting:
                    setting = SystemSetting(key="placement_active_group", value=group_name)
                    db.session.add(setting)
                else:
                    setting.value = group_name
                db.session.commit()
            _set_generation_status("success", f"Soru üretimi tamamlandı: {group_name} ({count} soru).", group_name)
        except Exception as exc:
            db.session.rollback()
            _set_generation_status("failed", f"Soru üretimi başarısız: {exc}", None)
        finally:
            db.session.remove()


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@require_roles("admin", "attache")
def users():
    form = UserForm()
    form.is_active.data = True
    if form.validate_on_submit():
        temp_password = _generate_password()
        identity_number = (form.identity_number.data or "").strip() or None
        if form.role.data == "teacher" and not identity_number:
            flash("Öğretmen rolü için T.C./IIN zorunludur.", "error")
            return redirect(url_for("admin.users"))
        if identity_number and User.query.filter_by(identity_number=identity_number).first():
            flash("Bu T.C./IIN ile kayıtlı bir kullanıcı zaten var.", "error")
            return redirect(url_for("admin.users"))
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            phone=form.phone.data,
            email=form.email.data,
            identity_number=identity_number,
            role=form.role.data,
            is_active=form.is_active.data,
            password_hash=bcrypt.generate_password_hash(temp_password).decode("utf-8"),
            must_change_password=True
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            actor_name_cached=current_user.full_name,
            actor_username_cached=current_user.username,
            action="create",
            entity_type="user",
            entity_id=user.id,
            after_json=serialize_json({"username": user.username})
        ))
        db.session.commit()
        session["last_temp_password"] = temp_password
        session["last_temp_username"] = user.username
        flash("Kullanıcı oluşturuldu. Geçici şifre hazır.", "success")
        return redirect(url_for("admin.users"))
    items = User.query.order_by(User.created_at.desc()).all()
    active_items = [u for u in items if u.is_active]
    inactive_items = [u for u in items if not u.is_active]
    return render_template(
        "admin/users.html",
        form=form,
        items=active_items,
        inactive_items=inactive_items
    )


@admin_bp.route("/users/clear-temp-password", methods=["POST"])
@login_required
@require_roles("admin")
def clear_temp_password():
    session.pop("last_temp_password", None)
    session.pop("last_temp_username", None)
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reset", methods=["POST"])
@login_required
@require_roles("admin")
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    temp_password = _generate_password()
    user.password_hash = bcrypt.generate_password_hash(temp_password).decode("utf-8")
    user.must_change_password = True
    db.session.commit()
    session["last_temp_password"] = temp_password
    session["last_temp_username"] = user.username
    flash("Şifre sıfırlandı. Geçici şifre hazır.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("admin")
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    if form.validate_on_submit():
        identity_number = (form.identity_number.data or "").strip() or None
        if form.role.data == "teacher" and not identity_number:
            flash("Öğretmen rolü için T.C./IIN zorunludur.", "error")
            return render_template("admin/edit_user.html", form=form, item=user)
        if identity_number:
            existing = User.query.filter_by(identity_number=identity_number).first()
            if existing and existing.id != user.id:
                flash("Bu T.C./IIN ile kayıtlı başka bir kullanıcı var.", "error")
                return render_template("admin/edit_user.html", form=form, item=user)
        user.username = form.username.data
        user.full_name = form.full_name.data
        user.phone = form.phone.data
        user.email = form.email.data
        user.identity_number = identity_number
        user.role = form.role.data
        user.is_active = form.is_active.data
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            actor_name_cached=current_user.full_name,
            actor_username_cached=current_user.username,
            action="update",
            entity_type="user",
            entity_id=user.id
        ))
        db.session.commit()
        flash("Kullanıcı güncellendi.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/edit_user.html", form=form, item=user)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_user(user_id):
    try:
        user = User.query.get_or_404(user_id)
        if user.id == current_user.id:
            flash("Kendi hesabınızı silemezsiniz.", "error")
            return redirect(url_for("admin.users"))
        blockers = []
        if Course.query.filter_by(created_by_user_id=user.id).first():
            blockers.append("oluşturduğu kurslar")
        if Course.query.filter_by(teacher_user_id=user.id).first():
            blockers.append("atanmış kurslar")
        if Teacher.query.filter_by(user_id=user.id).first():
            blockers.append("öğretmen kaydı")
        if Attendance.query.filter_by(marked_by_user_id=user.id).first():
            blockers.append("yoklama kayıtları")
        if Message.query.filter_by(user_id=user.id).first():
            blockers.append("mesajlar")
        if Announcement.query.filter_by(user_id=user.id).first():
            blockers.append("duyurular")
        if Certificate.query.filter_by(issued_by_user_id=user.id).first():
            blockers.append("sertifikalar")
        if CourseLedgerEntry.query.filter_by(teacher_user_id=user.id).first():
            blockers.append("kurs defteri kayıtları")
        if ApiToken.query.filter_by(user_id=user.id).first():
            blockers.append("API tokenlar")
        if blockers:
            flash(
                "Bu kullanıcı silinemiyor. İlişkili kayıtlar var: " + ", ".join(blockers) +
                ". Kullanıcıyı pasif yapın.",
                "error"
            )
            return redirect(url_for("admin.users"))
        logs = AuditLog.query.filter_by(actor_user_id=user.id).all()
        if logs:
            for log in logs:
                log.actor_name_cached = user.full_name
                log.actor_username_cached = user.username
                log.actor_user_id = None
                db.session.add(log)
        db.session.delete(user)
        db.session.commit()
        flash("Kullanıcı silindi.", "success")
        return redirect(url_for("admin.users"))
    except IntegrityError:
        db.session.rollback()
        flash("Kullanıcı silinemedi. İlişkili kayıtlar var. Lütfen kullanıcıyı pasif yapın.", "error")
        return redirect(url_for("admin.users"))
    except Exception:
        db.session.rollback()
        flash("Kullanıcı silme sırasında beklenmeyen bir hata oluştu.", "error")
        return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@require_roles("admin")
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id and user.is_active:
        flash("Kendi hesabınızı pasif yapamazsınız.", "error")
        return redirect(url_for("admin.users"))
    user.is_active = not user.is_active
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="status_update",
        entity_type="user",
        entity_id=user.id,
        after_json=serialize_json({"is_active": user.is_active})
    ))
    db.session.commit()
    flash("Kullanıcı durumu güncellendi.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@require_roles("admin", "coordinator")
def settings():
    if request.method == "POST":
        for key in ["whatsapp_provider", "n8n_webhook_url", "absence_threshold_ratio"]:
            value = request.form.get(key, "").strip()
            setting = SystemSetting.query.filter_by(key=key).first()
            if not setting:
                setting = SystemSetting(key=key, value=value)
                db.session.add(setting)
            else:
                setting.value = value
        db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="settings", entity_id=0))
        db.session.commit()
        flash("Ayarlar kaydedildi.", "success")
        return redirect(url_for("admin.settings"))

    settings = {s.key: s.value for s in SystemSetting.query.all()}
    return render_template("admin/settings.html", settings=settings)


@admin_bp.route("/assistant", methods=["GET", "POST"])
@login_required
@require_roles("admin", "coordinator")
def assistant_settings():
    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        changed = {"assistant_prompt_length": None}

        if action == "save_prompt":
            prompt_text = (request.form.get("assistant_prompt") or "").strip() or DEFAULT_LOGIN_ASSISTANT_PROMPT
            prompt_setting = SystemSetting.query.filter_by(key="login_assistant_prompt").first()
            if not prompt_setting:
                prompt_setting = SystemSetting(key="login_assistant_prompt", value=prompt_text)
                db.session.add(prompt_setting)
            else:
                prompt_setting.value = prompt_text
            changed["assistant_prompt_length"] = len(prompt_text)
            flash("Sistem promptu kaydedildi.", "success")
        else:
            flash("Geçersiz işlem.", "error")
            return redirect(url_for("admin.assistant_settings"))

        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="update",
            entity_type="assistant_settings",
            entity_id=0,
            after_json=serialize_json(changed)
        ))
        db.session.commit()
        return redirect(url_for("admin.assistant_settings"))

    prompt_setting = SystemSetting.query.filter_by(key="login_assistant_prompt").first()
    return render_template(
        "admin/assistant.html",
        assistant_prompt=(prompt_setting.value if prompt_setting else DEFAULT_LOGIN_ASSISTANT_PROMPT)
    )


@admin_bp.route("/audit-logs")
@login_required
@require_roles("admin", "coordinator")
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    user_ids = {log.actor_user_id for log in logs if log.actor_user_id}
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {user.id: user for user in users}
    return render_template("admin/audit_logs.html", logs=logs, user_map=user_map)


@admin_bp.route("/api-tokens", methods=["GET", "POST"])
@login_required
@require_roles("admin", "coordinator")
def api_tokens():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        name = (request.form.get("name") or "default").strip() or "default"
        user = User.query.filter_by(username=username).first()
        if not user:
            flash("Kullanıcı bulunamadı.", "error")
            return redirect(url_for("admin.api_tokens"))
        raw_token = secrets.token_urlsafe(32)
        token = ApiToken(
            user_id=user.id,
            name=name,
            token_hash=hash_api_token(raw_token),
            is_active=True
        )
        db.session.add(token)
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="create",
            entity_type="api_token",
            entity_id=0,
            after_json=serialize_json({"username": user.username, "name": name})
        ))
        db.session.commit()
        session["last_api_token"] = raw_token
        session["last_api_token_user"] = user.username
        flash("API token oluşturuldu.", "success")
        return redirect(url_for("admin.api_tokens"))

    token_user_ids = [row.user_id for row in ApiToken.query.distinct(ApiToken.user_id).all()]
    users = User.query.filter(User.id.in_(token_user_ids)).all() if token_user_ids else []
    user_map = {user.id: user for user in users}
    tokens = ApiToken.query.order_by(ApiToken.created_at.desc()).limit(200).all()
    return render_template("admin/api_tokens.html", tokens=tokens, user_map=user_map)


@admin_bp.route("/api-tokens/test-bot")
@login_required
@require_roles("admin", "coordinator")
def api_tokens_test_bot():
    raw_date = (request.args.get("date") or "").strip()
    if raw_date:
        try:
            target_date = datetime.fromisoformat(raw_date).date()
        except ValueError:
            return jsonify({"error": "invalid_date", "expected": "YYYY-MM-DD"}), 400
    else:
        target_date = datetime.utcnow().date()

    rows = (
        db.session.query(Session, Course)
        .join(Course, Course.id == Session.course_id)
        .filter(Session.session_date == target_date)
        .filter(Course.status == "active")
        .order_by(Course.title.asc(), Session.start_time.asc(), Session.id.asc())
        .all()
    )
    session_ids = [session.id for session, _ in rows]
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
    for session, course in rows:
        item = course_map.setdefault(course.id, {
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
        item["sessions"].append({
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

    return jsonify({
        "report_type": "daily_course_sessions",
        "date": target_date.isoformat(),
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_courses_count": int(total_active_courses),
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
    })


@admin_bp.route("/api-tokens/<int:token_id>/test")
@login_required
@require_roles("admin", "coordinator")
def api_token_test(token_id):
    token = ApiToken.query.get_or_404(token_id)
    if not token.is_active:
        return jsonify({"error": "token_inactive"}), 400
    if not token.user or token.user.role != "admin":
        return jsonify({"error": "forbidden", "message": "Sadece admin token test edilebilir."}), 403
    return api_tokens_test_bot()


@admin_bp.route("/api-tokens/<int:token_id>/revoke", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def revoke_api_token(token_id):
    token = ApiToken.query.get_or_404(token_id)
    token.is_active = False
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="revoke",
        entity_type="api_token",
        entity_id=token.id
    ))
    db.session.commit()
    flash("API token iptal edildi.", "success")
    return redirect(url_for("admin.api_tokens"))


@admin_bp.route("/api-tokens/clear-temp", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def clear_api_token():
    session.pop("last_api_token", None)
    session.pop("last_api_token_user", None)
    return redirect(url_for("admin.api_tokens"))


@admin_bp.route("/webhooks/n8n/test", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def n8n_test():
    payload = {
        "event_type": "test",
        "timestamp": datetime.utcnow().isoformat(),
        "actor_user_id": current_user.id,
        "data": {"message": "n8n test"}
    }
    result = emit_webhook("test", payload)
    flash(f"Webhook sonucu: {result.get('status')}", "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route("/year-rollover", methods=["GET", "POST"])
@login_required
@require_roles("admin")
def year_rollover():
    settings = {s.key: s.value for s in SystemSetting.query.all()}
    current_year = datetime.now().year
    month = datetime.now().month
    start_year = current_year if month >= 8 else current_year - 1
    current_academic = settings.get("academic_year") or f"{start_year}-{start_year + 1}"
    next_academic = f"{start_year + 1}-{start_year + 2}"

    if request.method == "POST":
        active_courses = Course.query.filter(Course.status == "active").all()
        for course in active_courses:
            course.status = "archived"

        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="year_rollover",
            entity_type="system",
            entity_id=0,
            after_json=serialize_json({
                "archived_courses": len(active_courses),
                "previous_academic_year": current_academic,
                "new_academic_year": next_academic
            })
        ))

        prev_setting = SystemSetting.query.filter_by(key="academic_year_previous").first()
        if not prev_setting:
            prev_setting = SystemSetting(key="academic_year_previous", value=current_academic)
            db.session.add(prev_setting)
        else:
            prev_setting.value = current_academic

        curr_setting = SystemSetting.query.filter_by(key="academic_year").first()
        if not curr_setting:
            curr_setting = SystemSetting(key="academic_year", value=next_academic)
            db.session.add(curr_setting)
        else:
            curr_setting.value = next_academic

        db.session.commit()
        flash(f"Yıl sonu işlemi tamamlandı. Arşivlenen aktif kurs: {len(active_courses)}", "success")
        return redirect(url_for("admin.year_rollover"))

    return render_template(
        "admin/year_rollover.html",
        current_academic_year=current_academic,
        next_academic_year=next_academic
    )


@admin_bp.route("/placement-questions")
@login_required
@require_roles("admin", "coordinator")
def placement_questions():
    return redirect(url_for("admin.placement_management", **request.args))


@admin_bp.route("/placement-management", methods=["GET", "POST"])
@login_required
@require_roles("admin", "coordinator")
def placement_management():
    generation_status = None
    group_filter = (request.args.get("group") or "").strip()
    skill = (request.args.get("skill") or "").strip()
    difficulty = (request.args.get("difficulty") or "").strip()
    search = (request.args.get("q") or "").strip()

    if request.method == "POST":
        updates = {}
        if "placement_prompt_override" in request.form:
            updates["placement_prompt_override"] = (request.form.get("placement_prompt_override") or "").strip()
        if "placement_active_group" in request.form:
            updates["placement_active_group"] = (request.form.get("placement_active_group") or "").strip()
        if "placement_prompt_override" in updates:
            prompt_text = updates["placement_prompt_override"]
            if prompt_text:
                db.session.add(PlacementPromptHistory(
                    prompt_text=prompt_text,
                    created_by_user_id=current_user.id
                ))
        for key, value in updates.items():
            setting = SystemSetting.query.filter_by(key=key).first()
            if not setting:
                setting = SystemSetting(key=key, value=value)
                db.session.add(setting)
            else:
                setting.value = value
        db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="placement_settings", entity_id=0))
        db.session.commit()
        flash("Seviye sınavı ayarları kaydedildi.", "success")
        return redirect(url_for("admin.placement_management"))

    settings = {s.key: s.value for s in SystemSetting.query.all()}
    generation_status = None
    raw_status = settings.get("placement_generation_status")
    if raw_status:
        try:
            generation_status = json.loads(raw_status)
        except Exception:
            generation_status = {"state": "unknown", "message": raw_status}
    prompt_history = PlacementPromptHistory.query.order_by(PlacementPromptHistory.created_at.desc()).limit(50).all()
    prompt_history_view = []
    for idx, item in enumerate(prompt_history):
        prompt_history_view.append({
            "id": item.id,
            "created_at": item.created_at,
            "prompt_text": item.prompt_text,
            "is_active": idx == 0
        })
    active_group = settings.get("placement_active_group", "")
    selected_group = group_filter or active_group
    query = PlacementQuestion.query.filter(PlacementQuestion.is_active.is_(True))
    if selected_group:
        query = query.filter(PlacementQuestion.group_name == selected_group)

    if skill:
        query = query.filter(PlacementQuestion.skill == skill)
    if difficulty:
        query = query.filter(PlacementQuestion.difficulty == difficulty)
    if search:
        query = query.filter(PlacementQuestion.prompt.ilike(f"%{search}%"))

    items = query.order_by(PlacementQuestion.created_at.desc()).all()
    group_rows = (
        db.session.query(
            PlacementQuestion.group_name,
            func.count(PlacementQuestion.id),
            func.max(PlacementQuestion.created_at)
        )
        .group_by(PlacementQuestion.group_name)
        .order_by(func.max(PlacementQuestion.created_at).desc())
        .all()
    )
    groups = [
        {"name": name, "count": count, "is_active": name == active_group}
        for name, count, _ in group_rows if name
    ]
    total_questions = PlacementQuestion.query.count()
    total_groups = len(groups)
    view_items = []
    for item in items:
        try:
            options = json.loads(item.options_json)
        except Exception:
            options = []
        view_items.append({
            "id": item.id,
            "skill": item.skill,
            "difficulty": item.difficulty,
            "prompt": item.prompt,
            "options": options,
            "correct_index": item.correct_index,
            "explanation": item.explanation,
            "is_active": item.is_active,
            "group_name": item.group_name
        })

    return render_template(
        "admin/placement_management.html",
        settings=settings,
        prompt_history=prompt_history_view,
        items=view_items,
        groups=groups,
        selected_group=selected_group,
        skill=skill,
        difficulty=difficulty,
        search=search,
        active_group=active_group,
        total_questions=total_questions,
        total_groups=total_groups,
        generation_status=generation_status
    )


@admin_bp.route("/placement-prompt/<int:history_id>/use", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def placement_prompt_use(history_id):
    item = PlacementPromptHistory.query.get_or_404(history_id)
    setting = SystemSetting.query.filter_by(key="placement_prompt_override").first()
    if not setting:
        setting = SystemSetting(key="placement_prompt_override", value=item.prompt_text)
        db.session.add(setting)
    else:
        setting.value = item.prompt_text
    db.session.add(PlacementPromptHistory(
        prompt_text=item.prompt_text,
        created_by_user_id=current_user.id
    ))
    db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="placement_prompt", entity_id=item.id))
    db.session.commit()
    flash("Prompt güncellendi.", "success")
    return redirect(url_for("admin.placement_management"))


@admin_bp.route("/placement-prompt/<int:history_id>/delete", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def placement_prompt_delete(history_id):
    item = PlacementPromptHistory.query.get_or_404(history_id)
    db.session.delete(item)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="delete",
        entity_type="placement_prompt",
        entity_id=item.id
    ))
    db.session.commit()
    flash("Prompt geçmiş kaydı silindi.", "success")
    return redirect(url_for("admin.placement_management"))


@admin_bp.route("/placement-prompt/delete-all", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def placement_prompt_delete_all():
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    if not bcrypt.check_password_hash(current_user.password_hash, password):
        flash("Şifre hatalı.", "error")
        return redirect(url_for("admin.placement_management"))
    if confirm != "yes":
        flash("Toplu silme için onay kutusunu işaretleyin.", "error")
        return redirect(url_for("admin.placement_management"))

    count = PlacementPromptHistory.query.count()
    PlacementPromptHistory.query.delete()
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="delete",
        entity_type="placement_prompt",
        entity_id=0,
        after_json=serialize_json({"deleted_count": count})
    ))
    db.session.commit()
    flash("Tüm prompt geçmişi silindi.", "success")
    return redirect(url_for("admin.placement_management"))


@admin_bp.route("/placement-management/refresh", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def placement_refresh_pool_admin():
    try:
        count = int(request.form.get("count") or 30)
    except ValueError:
        count = 30
    count = max(1, min(count, 100))
    set_active = bool(request.form.get("set_active"))
    try:
        _set_generation_status("queued", "Soru üretimi sıraya alındı.", None)
        app = current_app._get_current_object()
        thread = threading.Thread(target=_run_generation, args=(app, count, set_active), daemon=True)
        thread.start()
        flash("Soru üretimi başlatıldı. Durum kutusundan takip edin.", "error")
    except Exception as exc:
        db.session.rollback()
        _set_generation_status("failed", f"Soru üretimi başarısız: {exc}", None)
        flash(f"Soru üretimi başlatılamadı: {exc}", "error")

    return redirect(url_for("admin.placement_management"))


@admin_bp.route("/placement-management/<int:question_id>/delete", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def delete_placement_question(question_id):
    used_in_tests = PlacementTestQuestion.query.filter_by(question_id=question_id).first()
    used_in_answers = PlacementAnswer.query.filter_by(question_id=question_id).first()
    if used_in_tests or used_in_answers:
        flash("Bu soru daha önce sınavda kullanılmış. Silinemez.", "error")
        return redirect(url_for("admin.placement_management"))
    item = PlacementQuestion.query.get_or_404(question_id)
    db.session.delete(item)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="delete",
        entity_type="placement_question",
        entity_id=item.id
    ))
    db.session.commit()
    flash("Soru silindi.", "success")
    return redirect(url_for("admin.placement_management"))


@admin_bp.route("/placement-management/delete-many", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def delete_many_placement_questions():
    ids = request.form.getlist("question_ids")
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    if not bcrypt.check_password_hash(current_user.password_hash, password):
        flash("Şifre hatalı.", "error")
        return redirect(url_for("admin.placement_management"))
    if confirm != "yes":
        flash("Toplu silme için onay kutusunu işaretleyin.", "error")
        return redirect(url_for("admin.placement_management"))
    if not ids:
        flash("Silinecek soru seçilmedi.", "error")
        return redirect(url_for("admin.placement_management"))
    q_ids = [int(x) for x in ids if x.isdigit()]
    if not q_ids:
        flash("Geçersiz seçim.", "error")
        return redirect(url_for("admin.placement_management"))

    used_test_ids = {
        row[0] for row in db.session.query(PlacementTestQuestion.question_id)
        .filter(PlacementTestQuestion.question_id.in_(q_ids))
        .distinct()
        .all()
    }
    used_answer_ids = {
        row[0] for row in db.session.query(PlacementAnswer.question_id)
        .filter(PlacementAnswer.question_id.in_(q_ids))
        .distinct()
        .all()
    }
    blocked = used_test_ids | used_answer_ids
    deletable = [qid for qid in q_ids if qid not in blocked]
    if not deletable:
        flash("Seçili soruların tamamı sınavda kullanılmış. Silinemez.", "error")
        return redirect(url_for("admin.placement_management"))

    PlacementQuestion.query.filter(PlacementQuestion.id.in_(deletable)).delete(synchronize_session=False)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="delete_many",
        entity_type="placement_question",
        entity_id=0,
        after_json=serialize_json({"count": len(deletable)})
    ))
    db.session.commit()
    if blocked:
        flash(f"{len(deletable)} soru silindi. {len(blocked)} soru sınavda kullanıldığı için silinemedi.", "warning")
    else:
        flash(f"{len(deletable)} soru silindi.", "success")
    return redirect(url_for("admin.placement_management"))


@admin_bp.route("/pre-registrations")
@login_required
@require_roles("admin")
def pre_registrations():
    status = (request.args.get("status") or "pending").strip()
    search = (request.args.get("q") or "").strip()
    query = PreRegistration.query
    if status and status != "all":
        query = query.filter(PreRegistration.status == status)
    if search:
        query = query.filter(
            PreRegistration.full_name.ilike(f"%{search}%") |
            PreRegistration.iin.ilike(f"%{search}%") |
            PreRegistration.phone.ilike(f"%{search}%")
        )
    items = query.order_by(PreRegistration.created_at.desc()).all()
    counts = {
        "pending": PreRegistration.query.filter_by(status="pending").count(),
        "approved": PreRegistration.query.filter_by(status="approved").count(),
        "rejected": PreRegistration.query.filter_by(status="rejected").count()
    }
    return render_template(
        "admin/pre_registrations.html",
        items=items,
        status=status,
        search=search,
        counts=counts
    )


@admin_bp.route("/pre-registrations/pdf")
@login_required
@require_roles("admin")
def pre_registrations_pdf():
    status = (request.args.get("status") or "pending").strip()
    search = (request.args.get("q") or "").strip()
    query = PreRegistration.query
    if status and status != "all":
        query = query.filter(PreRegistration.status == status)
    if search:
        query = query.filter(
            PreRegistration.full_name.ilike(f"%{search}%") |
            PreRegistration.iin.ilike(f"%{search}%") |
            PreRegistration.phone.ilike(f"%{search}%")
        )
    items = query.order_by(PreRegistration.created_at.desc()).all()

    status_labels = {
        "pending": "Bekleyen",
        "approved": "Onaylı",
        "rejected": "Reddedilen",
        "all": "Tümü",
    }

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = _pdf_font_name()
    page_num = 1
    generated_at = datetime.now().strftime("%d.%m.%Y %H:%M")

    def footer():
        c.setFont(font_name, 8)
        c.drawString(40, 20, generated_at)
        c.drawRightString(width - 40, 20, f"Sayfa {page_num}")

    def trim(text, max_len):
        value = str(text or "")
        return value if len(value) <= max_len else f"{value[:max_len - 1]}…"

    def draw_header(start_y):
        c.setFont(font_name, 14)
        c.drawString(40, start_y, "Ön Kayıt Listesi")
        c.setFont(font_name, 9)
        c.drawString(40, start_y - 16, f"Durum: {status_labels.get(status, status)}")
        c.drawString(220, start_y - 16, f"Arama: {search or '-'}")
        c.drawRightString(width - 40, start_y - 16, f"Kayıt: {len(items)}")
        y = start_y - 36
        c.setFont(font_name, 9)
        c.drawString(40, y, "Tarih")
        c.drawString(98, y, "Ad Soyad")
        c.drawString(238, y, "IIN")
        c.drawString(318, y, "Telefon")
        c.drawString(394, y, "Seviye")
        c.drawString(466, y, "Durum")
        c.drawString(526, y, "E-posta")
        return y - 14

    y = draw_header(height - 40)
    c.setFont(font_name, 9)
    for item in items:
        if y < 60:
            footer()
            c.showPage()
            page_num += 1
            y = draw_header(height - 40)
            c.setFont(font_name, 9)
        created_at = item.created_at.strftime("%d.%m.%Y") if item.created_at else "-"
        c.drawString(40, y, created_at)
        c.drawString(98, y, trim(item.full_name, 26))
        c.drawString(238, y, trim(item.iin, 12))
        c.drawString(318, y, trim(item.phone, 14))
        c.drawString(394, y, trim(item.course_level, 10))
        c.drawString(466, y, status_labels.get(item.status, item.status))
        c.drawString(526, y, trim(item.email or "-", 18))
        y -= 14

    footer()
    c.save()
    buffer.seek(0)
    filename = f"pre_registrations_{status}_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


@admin_bp.route("/pre-registrations/<int:prereg_id>/status", methods=["POST"])
@login_required
@require_roles("admin")
def update_pre_registration_status(prereg_id):
    prereg = PreRegistration.query.get_or_404(prereg_id)
    new_status = (request.form.get("status") or "").strip()
    if new_status not in {"pending", "approved", "rejected"}:
        flash("Geçersiz durum.", "error")
        return redirect(url_for("admin.pre_registrations"))
    prereg.status = new_status
    db.session.add(prereg)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="update",
        entity_type="pre_registration",
        entity_id=prereg.id,
        after_json=serialize_json({"status": new_status})
    ))
    db.session.commit()
    flash("Ön kayıt durumu güncellendi.", "success")
    return redirect(url_for("admin.pre_registrations", status=request.args.get("status")))


@admin_bp.route("/placement-results")
@login_required
@require_roles("admin", "coordinator")
def placement_results():
    search = (request.args.get("q") or "").strip()
    group_filter = (request.args.get("group") or "").strip()
    level_filter = (request.args.get("level") or "").strip()
    min_score = request.args.get("min_score")
    max_score = request.args.get("max_score")
    date_from = (request.args.get("from") or "").strip()
    date_to = (request.args.get("to") or "").strip()

    group_subq = (
        db.session.query(
            PlacementTestQuestion.test_id.label("test_id"),
            func.max(PlacementQuestion.group_name).label("group_name")
        )
        .join(PlacementQuestion, PlacementQuestion.id == PlacementTestQuestion.question_id)
        .group_by(PlacementTestQuestion.test_id)
        .subquery()
    )
    rows = (
        db.session.query(PlacementTest, PlacementCandidate, group_subq.c.group_name)
        .join(PlacementCandidate, PlacementCandidate.id == PlacementTest.candidate_id)
        .outerjoin(group_subq, group_subq.c.test_id == PlacementTest.id)
    )
    if search:
        rows = rows.filter(
            (PlacementCandidate.full_name.ilike(f"%{search}%")) |
            (PlacementCandidate.iin.ilike(f"%{search}%"))
        )
    if group_filter:
        rows = rows.filter(group_subq.c.group_name == group_filter)
    if level_filter:
        rows = rows.filter(PlacementTest.level == level_filter)
    if min_score:
        try:
            rows = rows.filter(PlacementTest.score_percent >= float(min_score))
        except ValueError:
            pass
    if max_score:
        try:
            rows = rows.filter(PlacementTest.score_percent <= float(max_score))
        except ValueError:
            pass
    if date_from:
        try:
            rows = rows.filter(PlacementTest.started_at >= date_from)
        except Exception:
            pass
    if date_to:
        try:
            rows = rows.filter(PlacementTest.started_at <= date_to)
        except Exception:
            pass
    rows = rows.order_by(PlacementTest.started_at.desc()).limit(200).all()

    groups = [
        name for (name,) in db.session.query(PlacementQuestion.group_name)
        .distinct()
        .order_by(PlacementQuestion.group_name.asc())
        .all() if name
    ]
    total_tests = PlacementTest.query.count()
    avg_score = db.session.query(func.avg(PlacementTest.score_percent)).scalar() or 0
    items = []
    for test, candidate, group_name in rows:
        items.append({
            "id": test.id,
            "candidate": candidate.full_name,
            "iin": candidate.iin,
            "started_at": test.started_at,
            "completed_at": test.completed_at,
            "score_percent": test.score_percent,
            "level": test.level,
            "total_questions": test.total_questions,
            "group_name": group_name or "-",
            "mode": test.mode,
            "model_used": test.model_used
        })
    return render_template(
        "admin/placement_results.html",
        items=items,
        groups=groups,
        total_tests=total_tests,
        avg_score=round(avg_score, 2),
        search=search,
        group_filter=group_filter,
        level_filter=level_filter,
        min_score=min_score or "",
        max_score=max_score or "",
        date_from=date_from,
        date_to=date_to
    )


@admin_bp.route("/placement-results/<int:test_id>/delete", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def delete_placement_result(test_id):
    test = PlacementTest.query.get_or_404(test_id)
    candidate_id = test.candidate_id
    PlacementAnswer.query.filter_by(test_id=test.id).delete(synchronize_session=False)
    PlacementTestQuestion.query.filter_by(test_id=test.id).delete(synchronize_session=False)
    db.session.delete(test)
    db.session.commit()
    # delete candidate if no remaining tests
    remaining = PlacementTest.query.filter_by(candidate_id=candidate_id).count()
    if remaining == 0:
        candidate = PlacementCandidate.query.get(candidate_id)
        if candidate:
            db.session.delete(candidate)
            db.session.commit()
    flash("Sınav sonucu silindi.", "success")
    return redirect(url_for("admin.placement_results"))


@admin_bp.route("/placement-results/delete-many", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def delete_many_placement_results():
    ids = request.form.getlist("test_ids")
    password = request.form.get("password", "")
    confirm = request.form.get("confirm", "")
    if not bcrypt.check_password_hash(current_user.password_hash, password):
        flash("Şifre hatalı.", "error")
        return redirect(url_for("admin.placement_results"))
    if confirm != "yes":
        flash("Toplu silme için onay kutusunu işaretleyin.", "error")
        return redirect(url_for("admin.placement_results"))
    if not ids:
        flash("Silinecek sonuç seçilmedi.", "error")
        return redirect(url_for("admin.placement_results"))
    test_ids = [int(x) for x in ids if x.isdigit()]
    if not test_ids:
        flash("Geçersiz seçim.", "error")
        return redirect(url_for("admin.placement_results"))

    candidate_ids = [row[0] for row in db.session.query(PlacementTest.candidate_id).filter(PlacementTest.id.in_(test_ids)).all()]
    PlacementAnswer.query.filter(PlacementAnswer.test_id.in_(test_ids)).delete(synchronize_session=False)
    PlacementTestQuestion.query.filter(PlacementTestQuestion.test_id.in_(test_ids)).delete(synchronize_session=False)
    PlacementTest.query.filter(PlacementTest.id.in_(test_ids)).delete(synchronize_session=False)
    db.session.commit()

    # cleanup candidates without tests
    if candidate_ids:
        remaining_candidates = set(
            row[0] for row in db.session.query(PlacementTest.candidate_id)
            .filter(PlacementTest.candidate_id.in_(candidate_ids)).distinct().all()
        )
        to_delete = [cid for cid in candidate_ids if cid not in remaining_candidates]
        if to_delete:
            PlacementCandidate.query.filter(PlacementCandidate.id.in_(to_delete)).delete(synchronize_session=False)
            db.session.commit()

    flash(f"{len(test_ids)} sınav sonucu silindi.", "success")
    return redirect(url_for("admin.placement_results"))


@admin_bp.route("/placement-questions/<int:question_id>/approve", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def approve_placement_question(question_id):
    item = PlacementQuestion.query.get_or_404(question_id)
    item.is_active = True
    item.is_approved = True
    item.reviewed_at = datetime.utcnow()
    item.reviewed_by_user_id = current_user.id
    db.session.add(item)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="approve",
        entity_type="placement_question",
        entity_id=item.id
    ))
    db.session.commit()
    flash("Soru onaylandı.", "success")
    return redirect(url_for("admin.placement_management", **request.args))


@admin_bp.route("/placement-questions/<int:question_id>/reject", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def reject_placement_question(question_id):
    flash("Reddetme kapalıdır. Soru silme veya pasif yapma kullanın.", "error")
    return redirect(url_for("admin.placement_management"))


@admin_bp.route("/placement-questions/<int:question_id>/deactivate", methods=["POST"])
@login_required
@require_roles("admin", "coordinator")
def deactivate_placement_question(question_id):
    item = PlacementQuestion.query.get_or_404(question_id)
    item.is_active = False
    db.session.add(item)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="deactivate",
        entity_type="placement_question",
        entity_id=item.id
    ))
    db.session.commit()
    flash("Soru pasif yapıldı.", "success")
    return redirect(url_for("admin.placement_management", **request.args))




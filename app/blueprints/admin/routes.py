import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from ...extensions import db, bcrypt
import secrets
import string
from ...models import User, SystemSetting, AuditLog, Course
from ...forms import UserForm
from ...security import require_roles
from ...utils import serialize_json
from ...services.notifications import emit_webhook


admin_bp = Blueprint("admin", __name__)

def _generate_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%?"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@admin_bp.route("/users", methods=["GET", "POST"])
@login_required
@require_roles("admin")
def users():
    form = UserForm()
    form.is_active.data = True
    if form.validate_on_submit():
        temp_password = _generate_password()
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            phone=form.phone.data,
            email=form.email.data,
            role=form.role.data,
            is_active=form.is_active.data,
            password_hash=bcrypt.generate_password_hash(temp_password).decode("utf-8"),
            must_change_password=True
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="user", entity_id=user.id, after_json=serialize_json({"username": user.username})))
        db.session.commit()
        session["last_temp_password"] = temp_password
        session["last_temp_username"] = user.username
        flash("Kullanıcı oluşturuldu. Geçici şifre hazır.", "success")
        return redirect(url_for("admin.users"))
    items = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", form=form, items=items)


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
        user.username = form.username.data
        user.full_name = form.full_name.data
        user.phone = form.phone.data
        user.email = form.email.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        db.session.add(AuditLog(actor_user_id=current_user.id, action="update", entity_type="user", entity_id=user.id))
        db.session.commit()
        flash("Kullanıcı güncellendi.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/edit_user.html", form=form, item=user)


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Kendi hesabınızı silemezsiniz.", "error")
        return redirect(url_for("admin.users"))
    db.session.delete(user)
    db.session.commit()
    flash("Kullanıcı silindi.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@require_roles("admin")
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


@admin_bp.route("/audit-logs")
@login_required
@require_roles("admin")
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    user_ids = {log.actor_user_id for log in logs if log.actor_user_id}
    users = User.query.filter(User.id.in_(user_ids)).all() if user_ids else []
    user_map = {user.id: user for user in users}
    return render_template("admin/audit_logs.html", logs=logs, user_map=user_map)


@admin_bp.route("/webhooks/n8n/test", methods=["POST"])
@login_required
@require_roles("admin")
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

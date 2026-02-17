from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ...extensions import db, bcrypt
from ...models import Announcement, AuditLog
from ...security import require_roles
from ...utils import serialize_json


announcements_bp = Blueprint("announcements", __name__)


@announcements_bp.route("/", methods=["GET", "POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def index():
    if request.method == "POST":
        if current_user.role != "attache":
            flash("Duyuru oluşturma yetkiniz yok.", "error")
            return redirect(url_for("announcements.index"))
        content = (request.form.get("content") or "").strip()
        if not content:
            flash("Duyuru boş olamaz.", "error")
            return redirect(url_for("announcements.index"))
        if len(content) > 300:
            flash("Duyuru en fazla 300 karakter olabilir.", "error")
            return redirect(url_for("announcements.index"))
        note = Announcement(user_id=current_user.id, content=content)
        db.session.add(note)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="announcement", after_json=serialize_json({"length": len(content)})))
        db.session.commit()
        flash("Duyuru paylaşıldı.", "success")
        return redirect(url_for("announcements.index"))

    items = Announcement.query.order_by(Announcement.created_at.desc()).limit(200).all()
    return render_template("announcements/index.html", items=items)


@announcements_bp.route("/<int:announcement_id>/delete", methods=["POST"])
@login_required
@require_roles("admin", "attache")
def delete_announcement(announcement_id):
    note = Announcement.query.get_or_404(announcement_id)
    db.session.delete(note)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        action="delete",
        entity_type="announcement",
        entity_id=note.id
    ))
    db.session.commit()
    flash("Duyuru silindi.", "success")
    return redirect(url_for("announcements.index"))


@announcements_bp.route("/delete-many", methods=["POST"])
@login_required
@require_roles("admin", "attache")
def delete_many_announcements():
    ids = request.form.getlist("announcement_ids")
    password = request.form.get("password", "")
    if not bcrypt.check_password_hash(current_user.password_hash, password):
        flash("Şifre hatalı.", "error")
        return redirect(url_for("announcements.index"))
    if not ids:
        flash("Silinecek duyuru seçilmedi.", "error")
        return redirect(url_for("announcements.index"))
    ann_ids = [int(x) for x in ids if x.isdigit()]
    if not ann_ids:
        flash("Geçersiz seçim.", "error")
        return redirect(url_for("announcements.index"))
    Announcement.query.filter(Announcement.id.in_(ann_ids)).delete(synchronize_session=False)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="delete_many",
        entity_type="announcement",
        entity_id=0,
        after_json=serialize_json({"count": len(ann_ids)})
    ))
    db.session.commit()
    flash(f"{len(ann_ids)} duyuru silindi.", "success")
    return redirect(url_for("announcements.index"))

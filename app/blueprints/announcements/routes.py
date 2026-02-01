from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ...extensions import db
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

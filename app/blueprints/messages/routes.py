from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ...extensions import db
from ...models import Message, AuditLog
from ...security import require_roles
from ...utils import serialize_json


messages_bp = Blueprint("messages", __name__)


@messages_bp.route("/", methods=["GET", "POST"])
@login_required
@require_roles("teacher", "coordinator", "principal", "attache", "admin")
def index():
    if request.method == "POST":
        content = (request.form.get("content") or "").strip()
        if not content:
            flash("Mesaj boş olamaz.", "error")
            return redirect(url_for("messages.index"))
        if len(content) > 200:
            flash("Mesaj en fazla 200 karakter olabilir.", "error")
            return redirect(url_for("messages.index"))
        msg = Message(user_id=current_user.id, content=content)
        db.session.add(msg)
        db.session.add(AuditLog(actor_user_id=current_user.id, action="create", entity_type="message", after_json=serialize_json({"length": len(content)})))
        db.session.commit()
        flash("Mesajınız paylaşıldı.", "success")
        return redirect(url_for("messages.index"))

    items = Message.query.order_by(Message.created_at.desc()).limit(200).all()
    return render_template("messages/index.html", items=items)

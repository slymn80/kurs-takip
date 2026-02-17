from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from ...extensions import db, bcrypt
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


@messages_bp.route("/<int:message_id>/delete", methods=["POST"])
@login_required
@require_roles("admin", "attache")
def delete_message(message_id):
    msg = Message.query.get_or_404(message_id)
    db.session.delete(msg)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="delete",
        entity_type="message",
        entity_id=msg.id
    ))
    db.session.commit()
    flash("Mesaj silindi.", "success")
    return redirect(url_for("messages.index"))


@messages_bp.route("/delete-many", methods=["POST"])
@login_required
@require_roles("admin", "attache")
def delete_many_messages():
    ids = request.form.getlist("message_ids")
    password = request.form.get("password", "")
    if not bcrypt.check_password_hash(current_user.password_hash, password):
        flash("Şifre hatalı.", "error")
        return redirect(url_for("messages.index"))
    if not ids:
        flash("Silinecek mesaj seçilmedi.", "error")
        return redirect(url_for("messages.index"))
    msg_ids = [int(x) for x in ids if x.isdigit()]
    if not msg_ids:
        flash("Geçersiz seçim.", "error")
        return redirect(url_for("messages.index"))
    Message.query.filter(Message.id.in_(msg_ids)).delete(synchronize_session=False)
    db.session.add(AuditLog(
        actor_user_id=current_user.id,
        actor_name_cached=current_user.full_name,
        actor_username_cached=current_user.username,
        action="delete_many",
        entity_type="message",
        entity_id=0,
        after_json=serialize_json({"count": len(msg_ids)})
    ))
    db.session.commit()
    flash(f"{len(msg_ids)} mesaj silindi.", "success")
    return redirect(url_for("messages.index"))

from datetime import datetime, timedelta
from collections import deque
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from ...utils import serialize_json
from ...extensions import db, bcrypt
from ...models import User, AuditLog
from ...forms import LoginForm, ChangePasswordForm, PasswordUpdateForm


auth_bp = Blueprint("auth", __name__)

_login_attempts = {}


def _prune_attempts(ip, window_seconds):
    now = datetime.utcnow()
    dq = _login_attempts.get(ip, deque())
    while dq and (now - dq[0]).total_seconds() > window_seconds:
        dq.popleft()
    _login_attempts[ip] = dq
    return dq


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        ip = request.remote_addr or "unknown"
        window = current_app.config["LOGIN_RATE_LIMIT_WINDOW_SECONDS"]
        max_attempts = current_app.config["LOGIN_RATE_LIMIT_MAX"]
        dq = _prune_attempts(ip, window)
        if len(dq) >= max_attempts:
            flash("Çok fazla deneme. Lütfen biraz sonra tekrar deneyin.", "error")
            return render_template("auth/login.html", form=form)

        user = User.query.filter_by(username=form.username.data).first()
        if user and user.is_active and bcrypt.check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            if user.must_change_password:
                return redirect(url_for("auth.change_password"))
            return redirect(url_for("dashboard.index"))
        dq.append(datetime.utcnow())
        flash("Giriş bilgileri hatalı.", "error")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        current_user.password_hash = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        current_user.must_change_password = False
        db.session.add(current_user)
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="password_changed",
            entity_type="user",
            entity_id=current_user.id,
            after_json=serialize_json({"user_id": current_user.id})
        ))
        db.session.commit()
        flash("Şifre güncellendi.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/profile/password", methods=["GET", "POST"])
@login_required
def update_password():
    form = PasswordUpdateForm()
    if form.validate_on_submit():
        if not bcrypt.check_password_hash(current_user.password_hash, form.current_password.data):
            flash("Mevcut şifre hatalı.", "error")
            return render_template("auth/update_password.html", form=form)
        if form.new_password.data != form.confirm_password.data:
            flash("Yeni şifreler eşleşmiyor.", "error")
            return render_template("auth/update_password.html", form=form)
        current_user.password_hash = bcrypt.generate_password_hash(form.new_password.data).decode("utf-8")
        current_user.must_change_password = False
        db.session.add(current_user)
        db.session.add(AuditLog(
            actor_user_id=current_user.id,
            action="password_changed",
            entity_type="user",
            entity_id=current_user.id,
            after_json=serialize_json({"user_id": current_user.id})
        ))
        db.session.commit()
        flash("Şifre güncellendi.", "success")
        return redirect(url_for("dashboard.index"))
    return render_template("auth/update_password.html", form=form)

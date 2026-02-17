from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from .config import Config
from .extensions import db, login_manager, bcrypt, migrate, csrf
from .models import User


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config.get("SECRET_KEY") == "dev-secret" and not app.debug and not app.testing:
        raise RuntimeError("SECRET_KEY must be set to a secure value in production.")

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .blueprints.auth.routes import auth_bp
    from .blueprints.definitions.routes import definitions_bp
    from .blueprints.courses.routes import courses_bp
    from .blueprints.stats.routes import stats_bp
    from .blueprints.admin.routes import admin_bp
    from .blueprints.reports.routes import reports_bp
    from .blueprints.messages.routes import messages_bp
    from .blueprints.announcements.routes import announcements_bp
    from .blueprints.placement.routes import placement_bp
    from .blueprints.api.routes import api_bp
    from .blueprints.public.routes import public_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(definitions_bp, url_prefix="/definitions")
    app.register_blueprint(courses_bp, url_prefix="/courses")
    app.register_blueprint(stats_bp, url_prefix="/stats")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(messages_bp, url_prefix="/messages")
    app.register_blueprint(announcements_bp, url_prefix="/announcements")
    app.register_blueprint(placement_bp)
    csrf.exempt(api_bp)
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(public_bp)

    from .cli import register_cli
    register_cli(app)

    @app.route("/")
    def root():
        from flask_login import current_user
        from flask import redirect, url_for
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    from .blueprints.dashboard.routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    return app

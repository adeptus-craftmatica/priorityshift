import os
import sys

from flask import Flask

from app.config import Config
from app.extensions import csrf, db, login_manager, migrate, oauth


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(os.path.join(app.root_path, "..", "instance"), exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    # In a PyInstaller-frozen build, migration scripts live in the bundled
    # resource dir (sys._MEIPASS), not next to a real project checkout —
    # everywhere else (dev, tests, CLI) keeps Flask-Migrate's normal default.
    if getattr(sys, "frozen", False):
        migrate.init_app(app, db, directory=os.path.join(sys._MEIPASS, "migrations"))
    else:
        migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)

    # SSO stays dormant — and username/password login stays available either
    # way — until an admin supplies a real provider's credentials.
    if app.config.get("OIDC_CLIENT_ID") and app.config.get("OIDC_DISCOVERY_URL"):
        oauth.register(
            name="oidc",
            client_id=app.config["OIDC_CLIENT_ID"],
            client_secret=app.config["OIDC_CLIENT_SECRET"],
            server_metadata_url=app.config["OIDC_DISCOVERY_URL"],
            client_kwargs={"scope": "openid email profile"},
        )

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        # Flask-Login doesn't check `is_active` on its own — without this,
        # locking a user out only blocks *future* logins, not an existing
        # session. Returning None here forces an immediate re-login check.
        if user is None or not user.active:
            return None
        return user

    register_blueprints(app)
    register_cli(app)
    register_context_processors(app)
    register_error_handlers(app)
    register_request_hooks(app)

    return app


def register_request_hooks(app):
    from flask import redirect, request, url_for
    from flask_login import current_user

    @app.before_request
    def restrict_client_contacts_to_portal():
        # A client-contact account gets a deliberately narrow view — this
        # keeps them out of the internal app even if they guess a URL,
        # rather than relying on every internal route to check for it.
        if not current_user.is_authenticated or not current_user.is_client_contact:
            return None
        allowed_endpoints = {"portal.dashboard", "portal.project_detail", "portal.add_comment", "auth.logout", "static"}
        if request.endpoint not in allowed_endpoints:
            return redirect(url_for("portal.dashboard"))
        return None


def register_blueprints(app):
    from app.blueprints.main.routes import bp as main_bp
    from app.blueprints.auth.routes import bp as auth_bp
    from app.blueprints.dashboard.routes import bp as dashboard_bp
    from app.blueprints.projects.routes import bp as projects_bp
    from app.blueprints.chores.routes import bp as chores_bp
    from app.blueprints.ideas.routes import bp as ideas_bp
    from app.blueprints.priority.routes import bp as priority_bp
    from app.blueprints.comments.routes import bp as comments_bp
    from app.blueprints.requests.routes import bp as requests_bp
    from app.blueprints.admin.routes import bp as admin_bp
    from app.blueprints.reports.routes import bp as reports_bp
    from app.blueprints.attachments.routes import bp as attachments_bp
    from app.blueprints.calendar.routes import bp as calendar_bp
    from app.blueprints.deadline_approvals.routes import bp as deadline_approvals_bp
    from app.blueprints.portal.routes import bp as portal_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(chores_bp, url_prefix="/chores")
    app.register_blueprint(ideas_bp, url_prefix="/ideas")
    app.register_blueprint(priority_bp, url_prefix="/priority")
    app.register_blueprint(comments_bp, url_prefix="/comments")
    app.register_blueprint(requests_bp, url_prefix="/requests")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(attachments_bp, url_prefix="/attachments")
    app.register_blueprint(calendar_bp, url_prefix="/calendar")
    app.register_blueprint(deadline_approvals_bp, url_prefix="/deadline-approvals")
    app.register_blueprint(portal_bp, url_prefix="/portal")


def register_cli(app):
    from app.cli import register_cli_commands
    register_cli_commands(app)


def register_context_processors(app):
    from datetime import date

    from flask_login import current_user

    from app.models import Notification
    from app.services.permissions import PERMISSIONS

    @app.context_processor
    def inject_globals():
        unread_count = 0
        if current_user.is_authenticated:
            unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return {
            "unread_notification_count": unread_count,
            "all_permissions": PERMISSIONS,
            "now": date.today(),
            "sso_enabled": bool(app.config.get("OIDC_CLIENT_ID") and app.config.get("OIDC_DISCOVERY_URL")),
            "sso_provider_name": app.config.get("OIDC_PROVIDER_NAME", "SSO"),
        }


def register_error_handlers(app):
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/error.html", code=403, message="You don't have permission to do that."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/error.html", code=404, message="That page doesn't exist."), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/error.html", code=500, message="Something went wrong."), 500

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors/error.html", code=413, message="That file is too large (20MB max)."), 413

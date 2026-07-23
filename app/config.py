import os

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'priorityshift.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Overridable so the packaged desktop app can point this at a writable
    # per-user data directory instead of the (read-only, temp-extracted) app
    # bundle — see main.py's user_data_dir().
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(basedir, "instance", "uploads"))
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20 MB
    ALLOWED_UPLOAD_EXTENSIONS = {
        "pdf", "png", "jpg", "jpeg", "gif", "webp", "doc", "docx",
        "xls", "xlsx", "csv", "txt", "zip", "ppt", "pptx",
    }

    REMEMBER_COOKIE_DURATION_DAYS = 30
    SESSION_COOKIE_SAMESITE = "Lax"

    # Working-hierarchy defaults used by seed data / admin screens.
    DEFAULT_HIERARCHY_ROLES = [
        "President",
        "Vice President",
        "Director",
        "Manager",
        "Team Lead",
        "Employee",
    ]

    # Real notification delivery is off by default — this app runs fine with
    # in-app notifications only. Set NOTIFICATION_DELIVERY_ENABLED=true and
    # supply the relevant settings below to actually send email/Slack/Teams.
    NOTIFICATION_DELIVERY_ENABLED = os.environ.get("NOTIFICATION_DELIVERY_ENABLED", "false").lower() == "true"
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "priorityshift@example.com")
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
    TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL")

    # Generic OIDC SSO — dormant unless a provider's credentials are set.
    # The username/password login stays available either way.
    OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID")
    OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET")
    OIDC_DISCOVERY_URL = os.environ.get("OIDC_DISCOVERY_URL")
    OIDC_PROVIDER_NAME = os.environ.get("OIDC_PROVIDER_NAME", "SSO")

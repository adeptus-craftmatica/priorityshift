"""PriorityShift Control Panel — a desktop launcher so the app never has to
be run from a terminal. Start/stop the server, create your admin account,
and open the app, all from one window.

Runs Flask in-process (via werkzeug's own WSGI server on a background
thread) rather than shelling out to a separate `flask run` process — this
is what lets the whole thing be packaged into a single standalone
PriorityShift.app/.exe/binary with `release.py` + PyInstaller: a packaged
build has no project-local .venv to shell out to.

Run from source with the project's own virtualenv, e.g.:
    .venv/bin/python main.py
"""

import os
import sys
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout, QWidget,
)

PROJECT_DIR = Path(__file__).resolve().parent
HOST = "127.0.0.1"
# NOT 5000: on macOS (Monterey+), Apple's AirPlay Receiver (part of
# ControlCenter) listens on port 5000 by default. Our server would fail to
# bind it and crash immediately, and "Open in Browser" would actually be
# connecting to AirPlay Receiver instead of Flask — which looks exactly
# like a server that won't start and a browser tab that stays blank.
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    """Where bundled read-only resources (migration scripts, etc.) live.
    PyInstaller extracts/mounts data files here at runtime; from source it's
    just the project root."""
    if is_frozen():
        return Path(sys._MEIPASS)
    return PROJECT_DIR


def user_data_dir() -> Path:
    """Where the database and uploaded files actually live. A packaged app's
    own directory is treated as disposable (overwritten on every update, and
    on macOS may not even be writable) — real data has to live in the OS's
    normal per-user data location instead. Running from source keeps using
    the project's own instance/ folder, unchanged from before."""
    if not is_frozen():
        return PROJECT_DIR / "instance"
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "PriorityShift"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "PriorityShift"
    else:
        base = Path.home() / ".local" / "share" / "PriorityShift"
    base.mkdir(parents=True, exist_ok=True)
    return base


# Same palette as the web app's dark theme (slate neutrals + indigo brand)
# so the control panel and the product feel like one thing.
STYLESHEET = """
QMainWindow, QDialog {
    background-color: #0b1120;
}
QWidget {
    color: #e2e8f0;
    font-size: 13px;
}
QLabel {
    color: #e2e8f0;
    background: transparent;
}
QLabel#logo {
    background-color: #6366f1;
    color: white;
    font-size: 16px;
    font-weight: 700;
    border-radius: 10px;
}
QLabel#title {
    font-size: 21px;
    font-weight: 700;
    color: #f8fafc;
}
QLabel#subtitle {
    font-size: 12.5px;
    color: #94a3b8;
}
QLabel#sectionLabel {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
}
QLabel#footer {
    font-size: 12px;
    color: #64748b;
}
QFrame#card {
    background-color: #141b2d;
    border: 1px solid #1e293b;
    border-radius: 12px;
}
QFrame#divider {
    background-color: #1e293b;
    max-height: 1px;
    border: none;
}
QPushButton {
    background-color: #1a2338;
    border: 1px solid #2a3654;
    border-radius: 8px;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 500;
    color: #e2e8f0;
}
QPushButton:hover {
    background-color: #232e4a;
    border: 1px solid #3a4a70;
}
QPushButton:pressed {
    background-color: #18213a;
}
QPushButton:disabled {
    color: #475569;
    background-color: #141b2d;
    border: 1px solid #1e293b;
}
QPushButton#primary {
    background-color: #6366f1;
    border: 1px solid #6366f1;
    color: white;
    font-weight: 600;
}
QPushButton#primary:hover {
    background-color: #4f46e5;
    border: 1px solid #4f46e5;
}
QPushButton#primary:pressed {
    background-color: #4338ca;
}
QPushButton#primary:disabled {
    background-color: #312e81;
    border: 1px solid #312e81;
    color: #6b7280;
}
QPushButton#danger {
    color: #fca5a5;
    background-color: #1a2338;
    border: 1px solid #4c1d1d;
}
QPushButton#danger:hover {
    background-color: #2a1616;
    border: 1px solid #7f1d1d;
}
QPushButton#danger:disabled {
    color: #475569;
    background-color: #141b2d;
    border: 1px solid #1e293b;
}
QPlainTextEdit {
    background-color: #060a14;
    color: #94a3b8;
    border-radius: 10px;
    border: 1px solid #1e293b;
    padding: 10px;
    selection-background-color: #4338ca;
}
QLineEdit {
    background-color: #0b1120;
    padding: 8px 11px;
    border: 1px solid #2a3654;
    border-radius: 7px;
    font-size: 13px;
    color: #f1f5f9;
}
QLineEdit:focus {
    border: 1px solid #6366f1;
}
QMessageBox {
    background-color: #141b2d;
}
QScrollBar:vertical {
    background: #0b1120;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background: #2a3654;
    border-radius: 6px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #3a4a70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def port_open(host, port, timeout=0.3):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


class ServerThread(threading.Thread):
    """Runs the Flask app in-process via werkzeug's own WSGI server. Always
    a daemon thread, so it can never outlive this process the way the old
    QProcess-spawned `flask run` subprocess could — there's no more "orphaned
    server survives a force-quit" scenario to guard against."""

    def __init__(self, flask_app):
        super().__init__(daemon=True)
        from werkzeug.serving import make_server
        self.srv = make_server(HOST, PORT, flask_app, threaded=True)

    def run(self):
        self.srv.serve_forever()

    def shutdown(self):
        self.srv.shutdown()


class StatusDot(QLabel):
    def __init__(self):
        super().__init__()
        self.set_state("stopped")

    def set_state(self, state):
        colors = {"stopped": "#64748b", "starting": "#f59e0b", "running": "#34d399", "error": "#f87171"}
        color = colors.get(state, "#64748b")
        self.setStyleSheet(f"color: {color}; font-size: 15px; background: transparent;")
        self.setText("●")


class CreateAdminDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Admin Account")
        self.setMinimumWidth(380)

        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText("Jonathan Strachan")
        self.username = QLineEdit()
        self.username.setPlaceholderText("jonathan")
        self.email = QLineEdit()
        self.email.setPlaceholderText("jonathan@example.com")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.setSpacing(10)
        form.addRow("Full name", self.full_name)
        form.addRow("Username", self.username)
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        form.addRow("Confirm password", self.confirm_password)

        note = QLabel("This account gets the President role — full access to everything, including Admin.")
        note.setWordWrap(True)
        note.setObjectName("subtitle")

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        create_btn = QPushButton("Create Account")
        create_btn.setObjectName("primary")
        create_btn.setDefault(True)
        create_btn.clicked.connect(self.accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(create_btn)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def values(self):
        return {
            "full_name": self.full_name.text().strip(),
            "username": self.username.text().strip(),
            "email": self.email.text().strip(),
            "password": self.password.text(),
            "confirm_password": self.confirm_password.text(),
        }


class ControlPanel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PriorityShift Control Panel")
        self.setMinimumSize(660, 580)

        self.flask_app = None
        self.server_thread = None

        self._build_ui()

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self._poll_server_status)
        self.status_timer.start(1500)
        self._poll_server_status()
        self._refresh_database_status()

    # ---------- UI ----------

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout()
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(14)
        logo = QLabel("PS")
        logo.setObjectName("logo")
        logo.setFixedSize(44, 44)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        title = QLabel("PriorityShift")
        title.setObjectName("title")
        subtitle = QLabel("Control Panel — start the app, manage accounts, no terminal required.")
        subtitle.setObjectName("subtitle")
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        header.addWidget(logo)
        header.addLayout(title_block)
        header.addStretch()
        root.addLayout(header)

        # Status card
        status_card = QFrame()
        status_card.setObjectName("card")
        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(10)

        db_row = QHBoxLayout()
        self.db_dot = StatusDot()
        self.db_label = QLabel("Database: checking…")
        db_row.addWidget(self.db_dot)
        db_row.addWidget(self.db_label)
        db_row.addStretch()

        server_row = QHBoxLayout()
        self.server_dot = StatusDot()
        self.server_label = QLabel("Server: stopped")
        server_row.addWidget(self.server_dot)
        server_row.addWidget(self.server_label)
        server_row.addStretch()

        status_layout.addLayout(db_row)
        status_layout.addLayout(server_row)
        status_card.setLayout(status_layout)
        root.addWidget(status_card)

        # Server controls
        server_section = QLabel("SERVER")
        server_section.setObjectName("sectionLabel")
        root.addWidget(server_section)

        server_buttons = QHBoxLayout()
        server_buttons.setSpacing(10)
        self.start_btn = QPushButton("Start Server")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        self.open_btn = QPushButton("Open in Browser →")
        self.open_btn.clicked.connect(self.open_browser)
        self.open_btn.setEnabled(False)
        server_buttons.addWidget(self.start_btn)
        server_buttons.addWidget(self.stop_btn)
        server_buttons.addWidget(self.open_btn)
        root.addLayout(server_buttons)

        # Account controls
        account_section = QLabel("ACCOUNTS")
        account_section.setObjectName("sectionLabel")
        root.addWidget(account_section)

        account_buttons = QHBoxLayout()
        account_buttons.setSpacing(10)
        self.create_admin_btn = QPushButton("Create Admin Account")
        self.create_admin_btn.clicked.connect(self.create_admin_account)
        self.sample_data_btn = QPushButton("Load Sample Data")
        self.sample_data_btn.clicked.connect(self.load_sample_data)
        account_buttons.addWidget(self.create_admin_btn)
        account_buttons.addWidget(self.sample_data_btn)
        account_buttons.addStretch()
        root.addLayout(account_buttons)

        # Log console
        log_section = QLabel("ACTIVITY LOG")
        log_section.setObjectName("sectionLabel")
        root.addWidget(log_section)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        log_font = QFont("Menlo")
        log_font.setStyleHint(QFont.StyleHint.Monospace)
        log_font.setPointSize(11)
        self.log_console.setFont(log_font)
        root.addWidget(self.log_console, stretch=1)

        footer = QLabel(f"Local URL: {URL}")
        footer.setObjectName("footer")
        root.addWidget(footer)

        central.setLayout(root)
        self.setCentralWidget(central)

        self.log(f"Data directory: {user_data_dir()}")

    # ---------- Logging ----------

    def log(self, message):
        self.log_console.appendPlainText(message)
        self.log_console.moveCursor(QTextCursor.MoveOperation.End)

    # ---------- Flask app access ----------

    def _get_flask_app(self):
        if self.flask_app is None:
            if not is_frozen():
                sys.path.insert(0, str(PROJECT_DIR))
            else:
                # Point the app at a writable per-user location instead of
                # the bundled (disposable, possibly read-only) app directory.
                data_dir = user_data_dir()
                os.environ.setdefault("DATABASE_URL", f"sqlite:///{data_dir / 'priorityshift.db'}")
                os.environ.setdefault("UPLOAD_FOLDER", str(data_dir / "uploads"))
            from app import create_app
            self.flask_app = create_app()
        return self.flask_app

    def db_is_ready(self):
        try:
            with self._get_flask_app().app_context():
                from app.models import Role
                Role.query.first()
            return True
        except Exception:
            return False

    def ensure_db_initialized(self):
        """Creates tables on a fresh database and stamps it at the current
        Alembic revision, so a later schema upgrade (a new PriorityShift
        version with new migrations) still applies correctly instead of
        trying to recreate tables that already exist. Also always runs any
        pending migrations — a no-op on a database already at head, but
        what actually applies new migrations when someone upgrades from an
        older packaged version."""
        fresh = not self.db_is_ready()
        try:
            flask_app = self._get_flask_app()
            with flask_app.app_context():
                from flask_migrate import stamp, upgrade
                if fresh:
                    self.log("Initializing database…")
                    from app.extensions import db
                    db.create_all()
                    stamp()
                upgrade()
            if fresh:
                self.log("Database initialized.")
                self._refresh_database_status()
            return True
        except Exception as exc:
            self.log(f"Error initializing database: {exc}")
            QMessageBox.critical(self, "Couldn't initialize database", str(exc))
            return False

    def _refresh_database_status(self):
        if self.db_is_ready():
            self.db_dot.set_state("running")
            self.db_label.setText("Database: ready")
        else:
            self.db_dot.set_state("stopped")
            self.db_label.setText("Database: not initialized yet")

    # ---------- Server lifecycle ----------

    def start_server(self):
        if self.server_thread is not None:
            return
        if port_open(HOST, PORT):
            self.log(
                f"Port {PORT} is already in use by something else (maybe another "
                f"PriorityShift window, or a different app) — close it first."
            )
            return
        if not self.ensure_db_initialized():
            return

        self.log("Starting server…")
        self.server_dot.set_state("starting")
        self.server_label.setText("Server: starting…")
        self.start_btn.setEnabled(False)

        try:
            thread = ServerThread(self._get_flask_app())
            thread.start()
        except Exception as exc:
            self.log(f"Error starting server: {exc}")
            self.server_dot.set_state("error")
            self.server_label.setText("Server: failed to start")
            self.start_btn.setEnabled(True)
            return

        self.server_thread = thread
        self.stop_btn.setEnabled(True)

    def stop_server(self):
        if self.server_thread is not None:
            self.log("Stopping server…")
            self.server_thread.shutdown()
            self.server_thread.join(timeout=3)
            self.server_thread = None
            self.log("Stopped.")
        elif port_open(HOST, PORT):
            self.log(
                f"Port {PORT} is in use by something this window didn't start — "
                f"nothing to stop here. Close that instance/app yourself."
            )

        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.open_btn.setEnabled(False)
        self.server_dot.set_state("stopped")
        self.server_label.setText("Server: stopped")

    def _poll_server_status(self):
        running = port_open(HOST, PORT)
        if running:
            self.server_dot.set_state("running")
            self.open_btn.setEnabled(True)
            if self.server_thread is None:
                # Bound by something this window didn't start (another
                # PriorityShift window, most likely). We can't safely reach
                # across process/thread boundaries to manage it, so just
                # reflect reality rather than offering controls that would
                # silently do nothing.
                self.server_label.setText(f"Server: running at {URL} (not started by this window)")
                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(False)
            else:
                self.server_label.setText(f"Server: running at {URL}")
        elif self.server_thread is None:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.open_btn.setEnabled(False)
            self.server_dot.set_state("stopped")
            self.server_label.setText("Server: stopped")

    def open_browser(self):
        # Prefer Qt's own opener — on macOS it goes through Launch Services
        # directly. Python's `webbrowser` module instead drives the browser
        # via AppleScript/osascript, which silently fails to load the URL
        # (leaving a blank tab) if the app hasn't been granted Automation
        # permission in System Settings → Privacy & Security → Automation.
        opened = QDesktopServices.openUrl(QUrl(URL))
        if opened:
            self.log(f"Opened {URL} in your default browser.")
            return

        self.log("Qt couldn't hand off to the browser — trying `open` directly…")
        try:
            import subprocess
            subprocess.run(["open", URL], check=True)
            self.log(f"Opened {URL} via `open`.")
        except Exception as exc:
            self.log(f"Couldn't open the browser automatically: {exc}")
            QMessageBox.warning(
                self, "Couldn't open browser",
                f"Open this URL manually in your browser:\n\n{URL}",
            )

    # ---------- Accounts ----------

    def create_admin_account(self):
        if not self.ensure_db_initialized():
            return

        dialog = CreateAdminDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        if values["password"] != values["confirm_password"]:
            QMessageBox.warning(self, "Passwords don't match", "Password and confirmation must match.")
            return
        if len(values["password"]) < 6:
            QMessageBox.warning(self, "Password too short", "Use at least 6 characters.")
            return

        try:
            import seed
            with self._get_flask_app().app_context():
                user = seed.create_admin_user(
                    values["full_name"], values["username"], values["email"], values["password"],
                )
                # Grab plain values while the session is still bound — the
                # ORM object becomes detached the moment this context exits.
                username = user.username
            self.log(f"Created admin account: {username}")
            self._refresh_database_status()
            QMessageBox.information(
                self, "Account created",
                f"You're all set. Sign in at {URL} with username '{username}'.",
            )
        except Exception as exc:
            self.log(f"Error creating admin account: {exc}")
            QMessageBox.critical(self, "Couldn't create account", str(exc))

    def load_sample_data(self):
        if not self.ensure_db_initialized():
            return

        confirmed = QMessageBox.question(
            self, "Load sample data",
            "This adds demo departments, users, and sample projects/chores/ideas so you "
            "can see the app fully populated. It only does anything on an empty database "
            "— if you've already created an account, this is a no-op. Continue?",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        try:
            import seed
            with self._get_flask_app().app_context():
                seed.run_seed()
            self.log("Sample data load finished.")
            self._refresh_database_status()
            QMessageBox.information(self, "Done", "Sample data loaded (or already present).")
        except Exception as exc:
            self.log(f"Error loading sample data: {exc}")
            QMessageBox.critical(self, "Couldn't load sample data", str(exc))

    # ---------- Lifecycle ----------

    def closeEvent(self, event):
        if self.server_thread is not None:
            self.server_thread.shutdown()
            self.server_thread.join(timeout=2)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = ControlPanel()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

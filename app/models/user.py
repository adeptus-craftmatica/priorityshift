from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.mixins import TimestampMixin, utcnow

user_departments = db.Table(
    "user_departments",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("department_id", db.Integer, db.ForeignKey("departments.id"), primary_key=True),
)

user_teams = db.Table(
    "user_teams",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
    db.Column("team_id", db.Integer, db.ForeignKey("teams.id"), primary_key=True),
)


class Role(db.Model, TimestampMixin):
    """A position in the org hierarchy. Admins may rename roles, reorder the
    hierarchy, and edit which permissions each role grants."""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    hierarchy_level = db.Column(db.Integer, nullable=False)  # 1 = highest authority
    permissions = db.Column(db.JSON, nullable=False, default=list)
    description = db.Column(db.String(255))

    users = db.relationship("User", back_populates="role")

    def has_permission(self, key: str) -> bool:
        return key in (self.permissions or [])

    def __repr__(self):
        return f"<Role {self.name}>"


class Department(db.Model, TimestampMixin):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(255))

    users = db.relationship("User", secondary=user_departments, back_populates="departments")


class Team(db.Model, TimestampMixin):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(255))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    department = db.relationship("Department")
    users = db.relationship("User", secondary=user_teams, back_populates="teams")


class User(db.Model, UserMixin, TimestampMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(160), nullable=False)

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    team_lead_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Set only for external client contacts — marks this account as
    # restricted to the client portal (see app/blueprints/portal) rather
    # than the main internal app.
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id", use_alter=True, name="fk_users_client_id_clients"), nullable=True)

    capacity_hours_per_week = db.Column(db.Float, nullable=False, default=40.0)
    active = db.Column(db.Boolean, nullable=False, default=True)
    # Mirrors Project.is_archived: a permanent "this person is done" state
    # (e.g. left the company), distinct from a temporary lock-out. Archiving
    # always forces active=False; unarchiving restores it. Hidden from
    # default active-user lists, never deleted — see app/services/user_lifecycle.py.
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    avatar_color = db.Column(db.String(7), default="#6366f1")

    mfa_enabled = db.Column(db.Boolean, nullable=False, default=False)
    mfa_secret = db.Column(db.String(32), nullable=True)

    role = db.relationship("Role", back_populates="users")
    manager = db.relationship("User", remote_side=[id], foreign_keys=[manager_id])
    team_lead = db.relationship("User", remote_side=[id], foreign_keys=[team_lead_id])
    client = db.relationship("Client", foreign_keys=[client_id])

    departments = db.relationship("Department", secondary=user_departments, back_populates="users")
    teams = db.relationship("Team", secondary=user_teams, back_populates="users")

    @property
    def is_client_contact(self) -> bool:
        return self.client_id is not None

    def set_password(self, raw_password: str):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    def has_permission(self, key: str) -> bool:
        return bool(self.role and self.role.has_permission(key))

    def is_active_user(self) -> bool:
        return self.active

    @property
    def is_active(self):
        # Flask-Login's UserMixin field name; keep in sync with our `active` column.
        return self.active

    @property
    def initials(self) -> str:
        parts = self.full_name.split()
        if not parts:
            return self.username[:2].upper()
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    def __repr__(self):
        return f"<User {self.username}>"

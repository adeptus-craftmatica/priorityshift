from app.extensions import db
from app.models.mixins import TimestampMixin


class PriorityLevel(db.Model, TimestampMixin):
    """Admin-configurable priority levels (Critical, Urgent, High, Normal,
    Low, Paused by default). rank: lower number = higher priority."""

    __tablename__ = "priority_levels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(7), nullable=False, default="#6b7280")
    icon = db.Column(db.String(60), nullable=False, default="flag")
    requires_acknowledgment = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<PriorityLevel {self.name}>"


class ProjectPhase(db.Model, TimestampMixin):
    __tablename__ = "project_phases"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    rank = db.Column(db.Integer, nullable=False)
    is_terminal = db.Column(db.Boolean, nullable=False, default=False)
    active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<ProjectPhase {self.name}>"


class Tag(db.Model, TimestampMixin):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=False, default="#94a3b8")

    def __repr__(self):
        return f"<Tag {self.name}>"


project_tags = db.Table(
    "project_tags",
    db.Column("project_id", db.Integer, db.ForeignKey("projects.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)

chore_tags = db.Table(
    "chore_tags",
    db.Column("chore_id", db.Integer, db.ForeignKey("chores.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)

idea_tags = db.Table(
    "idea_tags",
    db.Column("idea_id", db.Integer, db.ForeignKey("ideas.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)


class Client(db.Model, TimestampMixin):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    account_owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)

    account_owner = db.relationship("User", foreign_keys=[account_owner_id])

    def __repr__(self):
        return f"<Client {self.name}>"


class WorkflowRule(db.Model, TimestampMixin):
    """Generic, admin-editable guardrail evaluated before a priority change
    commits (e.g. cap on how many Critical projects one developer can hold).
    New rule types can be added without a schema change since the tunable
    bits live in `config`."""

    __tablename__ = "workflow_rules"

    RULE_TYPES = (
        "max_critical_per_developer",
        "max_high_per_team",
        "require_exec_approval_for_critical",
        "require_reason_for_increase",
        "require_approval_for_deadline_push",
    )

    id = db.Column(db.Integer, primary_key=True)
    rule_type = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255))
    scope = db.Column(db.String(40), nullable=False, default="global")  # global | team | department
    threshold = db.Column(db.Integer, nullable=True)
    config = db.Column(db.JSON, nullable=False, default=dict)
    active = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<WorkflowRule {self.rule_type}>"


class SystemSetting(db.Model, TimestampMixin):
    __tablename__ = "system_settings"

    key = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.JSON, nullable=True)

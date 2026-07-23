from app.extensions import db
from app.models.catalog import project_tags
from app.models.mixins import TimestampMixin

CATEGORIES = (
    "standard", "maintenance", "emergency", "research", "infrastructure", "compliance",
)

HEALTH_STATUSES = (
    ("on_track", "Yes — On Track"),
    ("at_risk", "Maybe — At Risk"),
    ("off_track", "No — Off Track"),
)


class ProjectAssignment(db.Model):
    __tablename__ = "project_assignments"

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    is_lead = db.Column(db.Boolean, nullable=False, default=False)
    assigned_at = db.Column(db.DateTime, default=db.func.now())

    project = db.relationship("Project", back_populates="assignments")
    user = db.relationship("User")


class ProjectDependency(db.Model):
    __tablename__ = "project_dependencies"

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), primary_key=True)
    depends_on_project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), primary_key=True)

    project = db.relationship(
        "Project", foreign_keys=[project_id], back_populates="dependencies"
    )
    depends_on = db.relationship("Project", foreign_keys=[depends_on_project_id])


class Project(db.Model, TimestampMixin):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    project_number = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    is_client = db.Column(db.Boolean, nullable=False, default=False)
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    category = db.Column(db.String(30), nullable=False, default="standard")
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=True)

    priority_level_id = db.Column(db.Integer, db.ForeignKey("priority_levels.id"), nullable=False)
    original_priority_level_id = db.Column(db.Integer, db.ForeignKey("priority_levels.id"), nullable=False)
    phase_id = db.Column(db.Integer, db.ForeignKey("project_phases.id"), nullable=False)

    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    requesting_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approving_manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    date_requested = db.Column(db.Date, nullable=True)
    date_started = db.Column(db.Date, nullable=True)
    target_deadline = db.Column(db.Date, nullable=True)
    original_deadline = db.Column(db.Date, nullable=True)
    revised_deadline = db.Column(db.Date, nullable=True)

    estimated_effort_hours = db.Column(db.Float, nullable=True)
    actual_time_spent_hours = db.Column(db.Float, nullable=False, default=0.0)
    percent_complete = db.Column(db.Integer, nullable=False, default=0)

    last_activity_at = db.Column(db.DateTime, nullable=True)

    reprioritization_count = db.Column(db.Integer, nullable=False, default=0)
    interruption_count = db.Column(db.Integer, nullable=False, default=0)
    total_interruption_minutes = db.Column(db.Integer, nullable=False, default=0)
    deadline_revision_count = db.Column(db.Integer, nullable=False, default=0)

    health_status = db.Column(db.String(20), nullable=False, default="on_track")
    health_reason = db.Column(db.String(500))
    health_is_manual_override = db.Column(db.Boolean, nullable=False, default=False)

    risks = db.Column(db.Text)
    roadblocks = db.Column(db.Text)
    notes = db.Column(db.Text)
    related_links = db.Column(db.Text)

    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    origin_idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=True)

    priority_level = db.relationship("PriorityLevel", foreign_keys=[priority_level_id])
    original_priority_level = db.relationship("PriorityLevel", foreign_keys=[original_priority_level_id])
    phase = db.relationship("ProjectPhase")
    client = db.relationship("Client")
    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
    requesting_department = db.relationship("Department", foreign_keys=[requesting_department_id])
    owner = db.relationship("User", foreign_keys=[owner_id])
    approving_manager = db.relationship("User", foreign_keys=[approving_manager_id])

    assignments = db.relationship(
        "ProjectAssignment", back_populates="project", cascade="all, delete-orphan"
    )
    assignees = db.relationship(
        "User", secondary="project_assignments", viewonly=True
    )
    dependencies = db.relationship(
        "ProjectDependency",
        foreign_keys=[ProjectDependency.project_id],
        back_populates="project",
        cascade="all, delete-orphan",
    )
    tags = db.relationship("Tag", secondary=project_tags, backref="projects")

    @property
    def item_type(self):
        return "project"

    @property
    def is_active(self):
        return not self.is_archived and not (self.phase and self.phase.is_terminal)

    @property
    def health_label(self):
        return dict(HEALTH_STATUSES).get(self.health_status, self.health_status)

    def __repr__(self):
        return f"<Project {self.project_number}>"

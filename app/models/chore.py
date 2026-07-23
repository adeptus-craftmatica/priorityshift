from app.extensions import db
from app.models.catalog import chore_tags
from app.models.mixins import TimestampMixin

RECURRENCE_TYPES = (
    "daily", "weekly", "monthly", "quarterly", "annually",
    "specific_day_of_month", "specific_weekday", "custom", "one_time",
)

OCCURRENCE_STATUSES = ("pending", "completed", "skipped", "escalated", "reassigned")


class Chore(db.Model, TimestampMixin):
    __tablename__ = "chores"

    id = db.Column(db.Integer, primary_key=True)
    chore_number = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    assigned_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_team_id = db.Column(db.Integer, db.ForeignKey("teams.id"), nullable=True)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    priority_level_id = db.Column(db.Integer, db.ForeignKey("priority_levels.id"), nullable=False)

    recurrence_type = db.Column(db.String(30), nullable=False, default="one_time")
    recurrence_config = db.Column(db.JSON, nullable=False, default=dict)

    due_date = db.Column(db.Date, nullable=True)
    preferred_time_of_day = db.Column(db.Time, nullable=True)
    estimated_duration_minutes = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="active")  # active | paused | archived
    last_completed_at = db.Column(db.DateTime, nullable=True)
    next_scheduled_at = db.Column(db.Date, nullable=True)
    required_evidence = db.Column(db.Boolean, nullable=False, default=False)

    reprioritization_count = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text)
    origin_idea_id = db.Column(db.Integer, db.ForeignKey("ideas.id"), nullable=True)

    assigned_user = db.relationship("User", foreign_keys=[assigned_user_id])
    assigned_team = db.relationship("Team")
    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
    priority_level = db.relationship("PriorityLevel")
    tags = db.relationship("Tag", secondary=chore_tags, backref="chores")

    occurrences = db.relationship(
        "ChoreOccurrence", back_populates="chore", cascade="all, delete-orphan",
        order_by="desc(ChoreOccurrence.occurrence_date)",
    )

    @property
    def item_type(self):
        return "chore"

    @property
    def is_active(self):
        return self.status == "active"

    def __repr__(self):
        return f"<Chore {self.chore_number}>"


class ChoreOccurrence(db.Model, TimestampMixin):
    __tablename__ = "chore_occurrences"

    id = db.Column(db.Integer, primary_key=True)
    chore_id = db.Column(db.Integer, db.ForeignKey("chores.id"), nullable=False)
    occurrence_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")

    completed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    actual_duration_minutes = db.Column(db.Integer, nullable=True)

    skip_reason = db.Column(db.String(500))
    reassigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    escalated_at = db.Column(db.DateTime, nullable=True)
    escalated_reason = db.Column(db.String(500))

    notes = db.Column(db.Text)
    evidence_attachment_id = db.Column(db.Integer, db.ForeignKey("attachments.id"), nullable=True)

    chore = db.relationship("Chore", back_populates="occurrences")
    completed_by = db.relationship("User", foreign_keys=[completed_by_id])
    reassigned_to = db.relationship("User", foreign_keys=[reassigned_to_id])

    def __repr__(self):
        return f"<ChoreOccurrence chore={self.chore_id} date={self.occurrence_date}>"

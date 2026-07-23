from app.extensions import db
from app.models.mixins import utcnow

EVENT_TYPES = (
    "created", "assigned", "unassigned", "priority_changed", "deadline_changed",
    "status_changed", "phase_changed", "health_changed", "note_added",
    "comment_added", "file_uploaded", "roadblock_added", "approval",
    "time_entry", "completed", "reopened", "converted", "skipped",
    "escalated", "correction", "locked", "unlocked", "archived", "unarchived",
)


class ActivityLog(db.Model):
    """Immutable timeline entry for a work item (or a user account's own
    lifecycle — see item_type='user'). Admins may correct data elsewhere,
    but corrections append a new `correction` entry rather than mutating or
    deleting prior history."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)

    item_type = db.Column(db.String(20), nullable=False)  # 'project' | 'chore' | 'idea' | 'user'
    item_id = db.Column(db.Integer, nullable=False)

    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    event_type = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    event_metadata = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    actor = db.relationship("User")

    def __repr__(self):
        return f"<ActivityLog {self.item_type}#{self.item_id} {self.event_type}>"

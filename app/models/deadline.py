from app.extensions import db
from app.models.mixins import utcnow

DEADLINE_REVISION_STATUSES = ("approved", "pending", "rejected")


class DeadlineRevision(db.Model):
    """Every deadline change on a project, preserved permanently rather than
    overwriting the previous date. A revision that requires approval is
    inserted with status='pending' and does NOT touch the project's actual
    deadline fields until it's decided — approving it applies the change,
    rejecting it just closes out the request."""

    __tablename__ = "deadline_revisions"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)

    previous_deadline = db.Column(db.Date, nullable=True)
    new_deadline = db.Column(db.Date, nullable=True)
    changed_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    reason = db.Column(db.Text)

    priority_event_id = db.Column(db.Integer, db.ForeignKey("priority_events.id"), nullable=True)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    estimated_hours_lost = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="approved")
    decision_notes = db.Column(db.Text)
    decided_at = db.Column(db.DateTime, nullable=True)

    project = db.relationship("Project", backref="deadline_revisions")
    priority_event = db.relationship("PriorityEvent")
    changed_by = db.relationship("User", foreign_keys=[changed_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])

    def __repr__(self):
        return f"<DeadlineRevision project={self.project_id} -> {self.new_deadline}>"

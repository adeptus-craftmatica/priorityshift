from app.extensions import db
from app.models.mixins import utcnow


class Interruption(db.Model):
    """A logged interruption — tracked separately from normal project work
    so lost time and context-switching cost are measurable."""

    __tablename__ = "interruptions"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    interrupted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    new_task_description = db.Column(db.String(500))
    reason = db.Column(db.Text)

    start_time = db.Column(db.DateTime, default=utcnow, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    context_switch_minutes = db.Column(db.Integer, nullable=True)

    resumed_original = db.Column(db.Boolean, nullable=True)
    deadline_affected = db.Column(db.Boolean, nullable=False, default=False)
    notes = db.Column(db.Text)

    priority_event_id = db.Column(db.Integer, db.ForeignKey("priority_events.id"), nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])
    interrupted_by = db.relationship("User", foreign_keys=[interrupted_by_id])
    project = db.relationship("Project", backref="interruptions")
    priority_event = db.relationship("PriorityEvent")

    @property
    def is_open(self):
        return self.end_time is None

    def __repr__(self):
        return f"<Interruption user={self.user_id} start={self.start_time}>"

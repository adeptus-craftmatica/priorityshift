from app.extensions import db
from app.models.mixins import utcnow

priority_event_affected_users = db.Table(
    "priority_event_affected_users",
    db.Column("priority_event_id", db.Integer, db.ForeignKey("priority_events.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), primary_key=True),
)


class PriorityEvent(db.Model):
    """The permanent audit record for every priority change. Rows are
    insert-only — a priority change never silently overwrites history."""

    __tablename__ = "priority_events"

    id = db.Column(db.Integer, primary_key=True)

    item_type = db.Column(db.String(20), nullable=False)  # 'project' | 'chore'
    item_id = db.Column(db.Integer, nullable=False)

    occurred_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    previous_priority_level_id = db.Column(db.Integer, db.ForeignKey("priority_levels.id"), nullable=True)
    new_priority_level_id = db.Column(db.Integer, db.ForeignKey("priority_levels.id"), nullable=True)

    reason = db.Column(db.Text)
    business_justification = db.Column(db.Text)

    expected_interruption_minutes = db.Column(db.Integer, nullable=True)
    actual_interruption_minutes = db.Column(db.Integer, nullable=True)

    displaced_item_type = db.Column(db.String(20), nullable=True)
    displaced_item_id = db.Column(db.Integer, nullable=True)
    displaced_summary = db.Column(db.Text)

    estimated_impact = db.Column(db.Text)
    affected_deadline_note = db.Column(db.String(500))

    is_temporary = db.Column(db.Boolean, nullable=False, default=False)
    resume_date = db.Column(db.Date, nullable=True)

    developer_comment = db.Column(db.Text)
    developer_acknowledged_at = db.Column(db.DateTime, nullable=True)
    developer_acknowledged_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
    approved_by = db.relationship("User", foreign_keys=[approved_by_id])
    developer_acknowledged_by = db.relationship("User", foreign_keys=[developer_acknowledged_by_id])
    previous_priority_level = db.relationship("PriorityLevel", foreign_keys=[previous_priority_level_id])
    new_priority_level = db.relationship("PriorityLevel", foreign_keys=[new_priority_level_id])
    affected_developers = db.relationship("User", secondary=priority_event_affected_users)

    def __repr__(self):
        return f"<PriorityEvent {self.item_type}#{self.item_id} @ {self.occurred_at}>"

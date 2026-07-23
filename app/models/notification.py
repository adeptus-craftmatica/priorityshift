from app.extensions import db
from app.models.mixins import utcnow

NOTIFICATION_TYPES = (
    "assignment", "priority_change", "approval_request", "deadline_change",
    "deadline_upcoming", "overdue", "new_blocker", "comment_mention", "decision",
    "chore_due", "request_awaiting_ack", "capacity_conflict",
    "work_paused", "work_resumed",
)


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    type = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.String(500))
    link_url = db.Column(db.String(300))

    item_type = db.Column(db.String(20), nullable=True)
    item_id = db.Column(db.Integer, nullable=True)

    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User")

    def __repr__(self):
        return f"<Notification {self.type} -> user={self.user_id}>"

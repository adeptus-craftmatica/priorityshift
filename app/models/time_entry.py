from app.extensions import db
from app.models.mixins import utcnow


class TimeEntry(db.Model):
    """Hours logged by a user against a work item, tagged planned vs
    unplanned so workload reports can separate the two."""

    __tablename__ = "time_entries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    item_type = db.Column(db.String(20), nullable=False)  # 'project' | 'chore'
    item_id = db.Column(db.Integer, nullable=False)

    entry_date = db.Column(db.Date, nullable=False)
    hours = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(20), nullable=False, default="planned")  # planned | unplanned
    notes = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    user = db.relationship("User")

    def __repr__(self):
        return f"<TimeEntry user={self.user_id} {self.item_type}#{self.item_id} {self.hours}h>"

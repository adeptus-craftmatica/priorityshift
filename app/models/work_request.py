from app.extensions import db
from app.models.mixins import utcnow

REQUEST_STATUSES = (
    "new", "accepted", "rejected", "needs_clarification",
    "converted", "scheduled", "escalated",
)


class WorkRequest(db.Model):
    __tablename__ = "work_requests"

    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(20), unique=True, nullable=False)

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    business_need = db.Column(db.Text)

    requested_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    requesting_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    desired_completion_date = db.Column(db.Date, nullable=True)
    requested_priority_id = db.Column(db.Integer, db.ForeignKey("priority_levels.id"), nullable=True)

    is_client = db.Column(db.Boolean, nullable=False, default=False)
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    estimated_business_impact = db.Column(db.Text)

    approver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    related_project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)

    status = db.Column(db.String(30), nullable=False, default="new")
    decision_notes = db.Column(db.Text)
    decided_at = db.Column(db.DateTime, nullable=True)

    converted_to_type = db.Column(db.String(20), nullable=True)
    converted_to_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    requested_by = db.relationship("User", foreign_keys=[requested_by_id])
    requesting_department = db.relationship("Department")
    requested_priority = db.relationship("PriorityLevel")
    approver = db.relationship("User", foreign_keys=[approver_id])
    related_project = db.relationship("Project")

    def __repr__(self):
        return f"<WorkRequest {self.request_number}>"

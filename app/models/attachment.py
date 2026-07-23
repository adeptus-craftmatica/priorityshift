from app.extensions import db
from app.models.mixins import utcnow


class Attachment(db.Model):
    __tablename__ = "attachments"

    id = db.Column(db.Integer, primary_key=True)

    item_type = db.Column(db.String(20), nullable=False)  # 'project' | 'chore' | 'idea'
    item_id = db.Column(db.Integer, nullable=False)

    filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(120))
    size_bytes = db.Column(db.Integer)

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    uploaded_by = db.relationship("User")

    def __repr__(self):
        return f"<Attachment {self.filename}>"

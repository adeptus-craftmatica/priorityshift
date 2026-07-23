from app.extensions import db
from app.models.mixins import utcnow


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)

    item_type = db.Column(db.String(20), nullable=False)  # 'project' | 'chore' | 'idea'
    item_id = db.Column(db.Integer, nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    parent_comment_id = db.Column(db.Integer, db.ForeignKey("comments.id"), nullable=True)

    is_decision = db.Column(db.Boolean, nullable=False, default=False)
    is_blocker = db.Column(db.Boolean, nullable=False, default=False)
    is_pinned = db.Column(db.Boolean, nullable=False, default=False)

    # Internal discussion is the default — a comment only reaches the client
    # portal if a staff member (or the client themselves) explicitly marks it.
    client_visible = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    edited_at = db.Column(db.DateTime, nullable=True)

    author = db.relationship("User")
    replies = db.relationship("Comment", backref=db.backref("parent", remote_side=[id]))

    def __repr__(self):
        return f"<Comment {self.item_type}#{self.item_id} by={self.author_id}>"

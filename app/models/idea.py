from app.extensions import db
from app.models.catalog import idea_tags
from app.models.mixins import TimestampMixin

REVIEW_STATUSES = (
    "new", "under_review", "needs_more_information", "accepted",
    "deferred", "rejected", "converted_to_project", "converted_to_chore", "archived",
)


class Idea(db.Model, TimestampMixin):
    __tablename__ = "ideas"

    id = db.Column(db.Integer, primary_key=True)
    idea_number = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    submitted_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    submission_date = db.Column(db.Date, nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    potential_value = db.Column(db.Text)
    expected_benefit = db.Column(db.Text)
    possible_users_affected = db.Column(db.String(255))
    estimated_effort_hours = db.Column(db.Float, nullable=True)

    notes = db.Column(db.Text)
    votes_count = db.Column(db.Integer, nullable=False, default=0)
    review_status = db.Column(db.String(30), nullable=False, default="new")

    converted_to_type = db.Column(db.String(20), nullable=True)  # 'project' | 'chore'
    converted_to_id = db.Column(db.Integer, nullable=True)

    submitted_by = db.relationship("User", foreign_keys=[submitted_by_id])
    department = db.relationship("Department")
    tags = db.relationship("Tag", secondary=idea_tags, backref="ideas")

    related_ideas = db.relationship(
        "Idea",
        secondary="idea_relations",
        primaryjoin="Idea.id==idea_relations.c.idea_id",
        secondaryjoin="Idea.id==idea_relations.c.related_idea_id",
    )

    @property
    def item_type(self):
        return "idea"

    @property
    def is_converted(self):
        return self.converted_to_type is not None

    def __repr__(self):
        return f"<Idea {self.idea_number}>"


idea_relations = db.Table(
    "idea_relations",
    db.Column("idea_id", db.Integer, db.ForeignKey("ideas.id"), primary_key=True),
    db.Column("related_idea_id", db.Integer, db.ForeignKey("ideas.id"), primary_key=True),
)

from app.extensions import db
from app.models import Chore, Idea, Project, User


def global_search(query_text, limit=8):
    if not query_text or not query_text.strip():
        return {"projects": [], "chores": [], "ideas": [], "users": []}

    like = f"%{query_text.strip()}%"

    projects = (
        Project.query.filter(
            db.or_(
                Project.project_number.ilike(like),
                Project.title.ilike(like),
                Project.description.ilike(like),
                Project.notes.ilike(like),
            )
        ).limit(limit).all()
    )
    chores = (
        Chore.query.filter(
            db.or_(
                Chore.chore_number.ilike(like),
                Chore.title.ilike(like),
                Chore.description.ilike(like),
                Chore.notes.ilike(like),
            )
        ).limit(limit).all()
    )
    ideas = (
        Idea.query.filter(
            db.or_(
                Idea.idea_number.ilike(like),
                Idea.title.ilike(like),
                Idea.description.ilike(like),
            )
        ).limit(limit).all()
    )
    users = (
        User.query.filter(
            db.or_(User.full_name.ilike(like), User.username.ilike(like), User.email.ilike(like))
        ).limit(limit).all()
    )

    return {"projects": projects, "chores": chores, "ideas": ideas, "users": users}

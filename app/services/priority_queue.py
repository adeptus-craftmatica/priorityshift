"""Computes "what should this person work on next" for personal and
organization dashboards. Both dashboards share this single source of truth
so the numbers always agree."""

from datetime import date, timedelta

from app.extensions import db
from app.models import Chore, PriorityLevel, Project, ProjectAssignment, User


def _active_projects_for_user(user):
    return (
        Project.query.join(ProjectAssignment, ProjectAssignment.project_id == Project.id)
        .join(PriorityLevel, Project.priority_level_id == PriorityLevel.id)
        .filter(ProjectAssignment.user_id == user.id, Project.is_archived.is_(False))
        .all()
    )


def _active_chores_for_user(user):
    team_ids = [t.id for t in user.teams]
    query = Chore.query.filter(Chore.status == "active")
    if team_ids:
        query = query.filter(
            db.or_(Chore.assigned_user_id == user.id, Chore.assigned_team_id.in_(team_ids))
        )
    else:
        query = query.filter(Chore.assigned_user_id == user.id)
    return query.all()


def _work_item_entry(obj):
    if obj.item_type == "project":
        due = obj.target_deadline
    else:
        due = obj.due_date
    priority = obj.priority_level
    return {
        "type": obj.item_type,
        "id": obj.id,
        "number": obj.project_number if obj.item_type == "project" else obj.chore_number,
        "title": obj.title,
        "priority": priority,
        "priority_rank": priority.rank if priority else 999,
        "due_date": due,
        "is_overdue": bool(due and due < date.today()),
        "health_status": getattr(obj, "health_status", None),
        "obj": obj,
    }


def get_priority_queue_for_user(user):
    items = [_work_item_entry(p) for p in _active_projects_for_user(user) if p.is_active]
    items += [_work_item_entry(c) for c in _active_chores_for_user(user)]

    def sort_key(entry):
        due = entry["due_date"] or date.max
        return (entry["priority_rank"], due)

    items.sort(key=sort_key)
    return items


def get_top_priority_for_user(user):
    queue = get_priority_queue_for_user(user)
    return queue[0] if queue else None


def get_committed_hours_for_user(user, queue=None):
    queue = queue if queue is not None else get_priority_queue_for_user(user)
    assigned_active_projects = [e["obj"] for e in queue if e["type"] == "project"]
    return sum(
        (p.estimated_effort_hours or 0) * (1 - (p.percent_complete or 0) / 100)
        for p in assigned_active_projects
    )


def get_org_dashboard_rows(users=None):
    """One row per active user with their computed #1 priority item."""
    rows = []
    users = users if users is not None else User.query.filter_by(active=True).order_by(User.full_name).all()
    for user in users:
        queue = get_priority_queue_for_user(user)
        rows.append({
            "user": user,
            "top_item": queue[0] if queue else None,
            "queue_length": len(queue),
        })
    return rows


def get_org_totals():
    active_projects = Project.query.filter_by(is_archived=False).all()
    active_chores = Chore.query.filter_by(status="active").all()

    today = date.today()
    week_from_now = today + timedelta(days=7)

    by_priority = {}
    for p in active_projects:
        name = p.priority_level.name if p.priority_level else "Unassigned"
        by_priority[name] = by_priority.get(name, 0) + 1

    overdue = [p for p in active_projects if p.target_deadline and p.target_deadline < today]
    due_this_week = [
        p for p in active_projects
        if p.target_deadline and today <= p.target_deadline <= week_from_now
    ]
    at_risk = [p for p in active_projects if p.health_status == "at_risk"]
    off_track = [p for p in active_projects if p.health_status == "off_track"]
    blocked = [p for p in active_projects if p.roadblocks]

    chores_due_soon = [
        c for c in active_chores
        if c.next_scheduled_at and today <= c.next_scheduled_at <= week_from_now
    ]

    return {
        "total_active_projects": len(active_projects),
        "total_active_chores": len(active_chores),
        "by_priority": by_priority,
        "overdue_count": len(overdue),
        "due_this_week_count": len(due_this_week),
        "at_risk_count": len(at_risk),
        "off_track_count": len(off_track),
        "blocked_count": len(blocked),
        "chores_due_soon_count": len(chores_due_soon),
    }

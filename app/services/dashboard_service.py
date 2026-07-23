"""Composes the personal dashboard: everything a user needs to answer
"what should I work on next" plus enough context (capacity, interruptions,
recent history) to explain why."""

from datetime import date, timedelta

from app.models import ActivityLog, Idea, PriorityEvent, Project, TimeEntry
from app.services.notifications import generate_due_reminders_for_user
from app.services.priority_queue import get_committed_hours_for_user, get_priority_queue_for_user


def get_personal_dashboard_context(user):
    queue = get_priority_queue_for_user(user)
    today = date.today()
    week_out = today + timedelta(days=7)

    overdue = [e for e in queue if e["is_overdue"]]
    due_today = [e for e in queue if e["due_date"] == today]
    due_this_week = [e for e in queue if e["due_date"] and today < e["due_date"] <= week_out]
    at_risk = [e for e in queue if e["health_status"] == "at_risk"]
    blocked = [e for e in queue if e["type"] == "project" and e["obj"].roadblocks]

    recent_events = (
        PriorityEvent.query.filter(
            PriorityEvent.affected_developers.any(id=user.id),
            PriorityEvent.occurred_at >= (today - timedelta(days=14)),
        )
        .order_by(PriorityEvent.occurred_at.desc())
        .limit(8)
        .all()
    )

    pending_acknowledgment = [
        e for e in PriorityEvent.query.filter(
            PriorityEvent.affected_developers.any(id=user.id),
            PriorityEvent.developer_acknowledged_at.is_(None),
        ).order_by(PriorityEvent.occurred_at.desc()).limit(20).all()
    ]

    since = today - timedelta(days=30)
    time_entries = TimeEntry.query.filter(
        TimeEntry.user_id == user.id, TimeEntry.entry_date >= since
    ).all()
    planned_hours = sum(t.hours for t in time_entries if t.category == "planned")
    unplanned_hours = sum(t.hours for t in time_entries if t.category == "unplanned")

    committed_hours = get_committed_hours_for_user(user, queue=queue)
    available_hours = max(0.0, (user.capacity_hours_per_week or 40) - committed_hours)

    generate_due_reminders_for_user(user, queue)

    recent_activity = (
        ActivityLog.query.filter(ActivityLog.actor_id == user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
        .all()
    )

    my_ideas = (
        Idea.query.filter_by(submitted_by_id=user.id)
        .order_by(Idea.created_at.desc())
        .limit(5)
        .all()
    )

    return {
        "queue": queue,
        "top_item": queue[0] if queue else None,
        "overdue": overdue,
        "due_today": due_today,
        "due_this_week": due_this_week,
        "at_risk": at_risk,
        "blocked": blocked,
        "recent_events": recent_events,
        "pending_acknowledgment": pending_acknowledgment,
        "planned_hours": planned_hours,
        "unplanned_hours": unplanned_hours,
        "committed_hours": round(committed_hours, 1),
        "available_hours": round(available_hours, 1),
        "capacity_hours": user.capacity_hours_per_week,
        "recent_activity": recent_activity,
        "my_ideas": my_ideas,
    }

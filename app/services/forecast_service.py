"""Projects each developer's workload over the coming weeks, so an overload
can be seen before a deadline is missed rather than after. Built on the same
capacity/interruption data already tracked for get_projected_completion() —
just aggregated across a person's whole queue instead of one project, and
spread across a multi-week window instead of collapsed into a single date."""

from datetime import date, timedelta

from app.extensions import db
from app.models import Interruption, User
from app.services.priority_queue import get_priority_queue_for_user

LOOKBACK_WEEKS = 8


def _historical_interruption_hours_per_week(user):
    cutoff = date.today() - timedelta(weeks=LOOKBACK_WEEKS)
    interruptions = Interruption.query.filter(
        Interruption.user_id == user.id, Interruption.start_time >= cutoff,
    ).all()
    if not interruptions:
        return 0.0
    total_minutes = sum((i.duration_minutes or 0) + (i.context_switch_minutes or 0) for i in interruptions)
    return round((total_minutes / 60.0) / LOOKBACK_WEEKS, 1)


def get_developer_forecast(user, weeks_ahead=8):
    today = date.today()
    interruption_hours_per_week = _historical_interruption_hours_per_week(user)
    effective_capacity_per_week = max(1.0, (user.capacity_hours_per_week or 0) - interruption_hours_per_week)

    weeks = [
        {"week_start": today + timedelta(weeks=i), "project_hours": 0.0, "chore_hours": 0.0}
        for i in range(weeks_ahead)
    ]

    queue = get_priority_queue_for_user(user)
    total_remaining_hours = 0.0

    for entry in queue:
        obj = entry["obj"]
        if entry["type"] == "project":
            remaining_hours = (obj.estimated_effort_hours or 0) * (1 - (obj.percent_complete or 0) / 100)
            if remaining_hours <= 0:
                continue
            total_remaining_hours += remaining_hours
            deadline = obj.revised_deadline or obj.target_deadline
            weeks_until_deadline = max(1, -(-(deadline - today).days // 7)) if deadline else weeks_ahead
            span = min(weeks_until_deadline, weeks_ahead)
            hours_per_week = remaining_hours / weeks_until_deadline
            for i in range(span):
                weeks[i]["project_hours"] += hours_per_week
        else:
            due = entry["due_date"]
            if not due or obj.estimated_duration_minutes is None:
                continue
            week_index = max(0, (due - today).days // 7)
            if week_index < weeks_ahead:
                weeks[week_index]["chore_hours"] += obj.estimated_duration_minutes / 60.0

    for w in weeks:
        w["total_hours"] = round(w["project_hours"] + w["chore_hours"], 1)
        w["project_hours"] = round(w["project_hours"], 1)
        w["chore_hours"] = round(w["chore_hours"], 1)
        w["capacity"] = round(effective_capacity_per_week, 1)
        w["overloaded"] = w["total_hours"] > effective_capacity_per_week

    weeks_of_backlog = round(total_remaining_hours / effective_capacity_per_week, 1) if total_remaining_hours else 0.0

    return {
        "user": user,
        "weeks": weeks,
        "effective_capacity_per_week": round(effective_capacity_per_week, 1),
        "interruption_hours_per_week": interruption_hours_per_week,
        "weeks_of_backlog": weeks_of_backlog,
        "overloaded_week_count": sum(1 for w in weeks if w["overloaded"]),
    }


def get_org_forecast(weeks_ahead=8, users=None):
    users = users if users is not None else User.query.filter_by(active=True).order_by(User.full_name).all()
    developer_forecasts = [get_developer_forecast(u, weeks_ahead) for u in users]

    if not developer_forecasts:
        org_weeks = [
            {"week_start": date.today() + timedelta(weeks=i), "total_hours": 0.0, "capacity": 0.0, "overloaded": False}
            for i in range(weeks_ahead)
        ]
    else:
        org_weeks = []
        for i in range(weeks_ahead):
            week = {
                "week_start": developer_forecasts[0]["weeks"][i]["week_start"],
                "total_hours": round(sum(f["weeks"][i]["total_hours"] for f in developer_forecasts), 1),
                "capacity": round(sum(f["weeks"][i]["capacity"] for f in developer_forecasts), 1),
            }
            week["overloaded"] = week["total_hours"] > week["capacity"]
            org_weeks.append(week)

    at_risk = sorted(
        [f for f in developer_forecasts if f["overloaded_week_count"] > 0 or f["weeks_of_backlog"] > weeks_ahead],
        key=lambda f: (-f["overloaded_week_count"], -f["weeks_of_backlog"]),
    )

    return {
        "developer_forecasts": developer_forecasts,
        "org_weeks": org_weeks,
        "at_risk": at_risk,
    }

"""Builds a month-grid of project deadlines and chore due dates. Kept as a
plain server-rendered grid (no external calendar JS library) so it fits the
same "no build step required" philosophy as the rest of the app."""

import calendar as calendar_module
from datetime import date, timedelta

from app.models import Chore, Project


def get_month_grid(year, month):
    first_of_month = date(year, month, 1)
    days_in_month = calendar_module.monthrange(year, month)[1]
    last_of_month = date(year, month, days_in_month)

    # Weeks start Monday; pad out to full weeks so the grid is always
    # rectangular, including the leading/trailing days of neighboring months.
    grid_start = first_of_month - timedelta(days=first_of_month.weekday())
    weeks_needed = -(-(days_in_month + first_of_month.weekday()) // 7)
    grid_end = grid_start + timedelta(days=weeks_needed * 7 - 1)

    projects = (
        Project.query.filter(Project.is_archived.is_(False))
        .filter(Project.target_deadline.isnot(None))
        .filter(Project.target_deadline >= grid_start, Project.target_deadline <= grid_end)
        .all()
    )
    chores = (
        Chore.query.filter(Chore.status == "active")
        .filter(Chore.next_scheduled_at.isnot(None))
        .filter(Chore.next_scheduled_at >= grid_start, Chore.next_scheduled_at <= grid_end)
        .all()
    )

    projects_by_day = {}
    for p in projects:
        deadline = p.revised_deadline or p.target_deadline
        projects_by_day.setdefault(deadline, []).append(p)
    chores_by_day = {}
    for c in chores:
        chores_by_day.setdefault(c.next_scheduled_at, []).append(c)

    today = date.today()
    weeks = []
    current = grid_start
    for _ in range(weeks_needed):
        week = []
        for _ in range(7):
            week.append({
                "date": current,
                "in_month": current.month == month,
                "is_today": current == today,
                "is_past": current < today,
                "projects": projects_by_day.get(current, []),
                "chores": chores_by_day.get(current, []),
            })
            current += timedelta(days=1)
        weeks.append(week)

    prev_month_date = first_of_month - timedelta(days=1)
    next_month_date = last_of_month + timedelta(days=1)

    return {
        "weeks": weeks,
        "month_label": first_of_month.strftime("%B %Y"),
        "year": year,
        "month": month,
        "prev_year": prev_month_date.year,
        "prev_month": prev_month_date.month,
        "next_year": next_month_date.year,
        "next_month": next_month_date.month,
    }

import calendar
from datetime import date, timedelta

from app.extensions import db
from app.models import ChoreOccurrence
from app.services.activity import log_activity


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _next_specific_day_of_month(from_date: date, day_of_month: int) -> date:
    year, month = from_date.year, from_date.month
    day = min(day_of_month, calendar.monthrange(year, month)[1])
    candidate = date(year, month, day)
    if candidate <= from_date:
        return _add_months(candidate, 1)
    return candidate


def _next_weekday(from_date: date, weekday: int) -> date:
    days_ahead = (weekday - from_date.weekday()) % 7
    days_ahead = days_ahead or 7
    return from_date + timedelta(days=days_ahead)


def compute_next_occurrence(chore, from_date=None):
    from_date = from_date or date.today()
    cfg = chore.recurrence_config or {}
    rtype = chore.recurrence_type

    if rtype == "daily":
        return from_date + timedelta(days=1)
    if rtype == "weekly":
        return from_date + timedelta(weeks=1)
    if rtype == "monthly":
        return _add_months(from_date, 1)
    if rtype == "quarterly":
        return _add_months(from_date, 3)
    if rtype == "annually":
        return _add_months(from_date, 12)
    if rtype == "specific_day_of_month":
        return _next_specific_day_of_month(from_date, cfg.get("day_of_month", 1))
    if rtype == "specific_weekday":
        return _next_weekday(from_date, cfg.get("weekday", 0))
    if rtype == "custom":
        return from_date + timedelta(days=cfg.get("interval_days", 30))
    return None  # one_time


def generate_occurrence_if_due(chore, today=None):
    today = today or date.today()
    if chore.status != "active" or chore.recurrence_type == "one_time":
        return None

    occurrence_date = chore.next_scheduled_at or chore.due_date or today
    if occurrence_date > today:
        return None

    existing = ChoreOccurrence.query.filter_by(chore_id=chore.id, occurrence_date=occurrence_date).first()
    if existing:
        return existing

    occurrence = ChoreOccurrence(chore_id=chore.id, occurrence_date=occurrence_date, status="pending")
    db.session.add(occurrence)
    log_activity("chore", chore.id, "created", f"Occurrence generated for {occurrence_date}")
    chore.next_scheduled_at = compute_next_occurrence(chore, occurrence_date)
    return occurrence


def complete_occurrence(occurrence, user, actual_duration_minutes=None, notes=None, evidence_attachment_id=None):
    occurrence.status = "completed"
    occurrence.completed_by_id = user.id
    occurrence.completed_at = db.func.now()
    occurrence.actual_duration_minutes = actual_duration_minutes
    occurrence.notes = notes
    occurrence.evidence_attachment_id = evidence_attachment_id

    chore = occurrence.chore
    chore.last_completed_at = db.func.now()
    if not chore.next_scheduled_at or chore.next_scheduled_at <= occurrence.occurrence_date:
        chore.next_scheduled_at = compute_next_occurrence(chore, occurrence.occurrence_date)

    log_activity(
        "chore", chore.id, "completed",
        f"Occurrence for {occurrence.occurrence_date} completed by {user.full_name}", actor=user,
    )
    return occurrence


def skip_occurrence(occurrence, user, reason):
    occurrence.status = "skipped"
    occurrence.skip_reason = reason
    chore = occurrence.chore
    if not chore.next_scheduled_at:
        chore.next_scheduled_at = compute_next_occurrence(chore, occurrence.occurrence_date)
    log_activity(
        "chore", chore.id, "skipped",
        f"Occurrence for {occurrence.occurrence_date} skipped by {user.full_name}: {reason}", actor=user,
    )
    return occurrence


def reassign_occurrence(occurrence, user, new_user):
    occurrence.reassigned_to_id = new_user.id
    occurrence.status = "reassigned"
    log_activity(
        "chore", occurrence.chore_id, "assigned",
        f"Occurrence for {occurrence.occurrence_date} reassigned from "
        f"{occurrence.chore.assigned_user.full_name if occurrence.chore.assigned_user else 'team'} to {new_user.full_name}",
        actor=user,
    )
    return occurrence


def generate_due_occurrences_for_all(today=None):
    from app.models import Chore

    today = today or date.today()
    created = []
    for chore in Chore.query.filter_by(status="active").all():
        occurrence = generate_occurrence_if_due(chore, today=today)
        if occurrence:
            created.append(occurrence)
    return created


def escalate_occurrence(occurrence, user, reason):
    occurrence.status = "escalated"
    occurrence.escalated_at = db.func.now()
    occurrence.escalated_reason = reason
    log_activity(
        "chore", occurrence.chore_id, "escalated",
        f"Occurrence for {occurrence.occurrence_date} escalated by {user.full_name}: {reason}", actor=user,
    )
    return occurrence

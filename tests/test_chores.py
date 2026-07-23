from datetime import date

from app.models import ChoreOccurrence
from app.services.chore_service import (
    compute_next_occurrence, generate_occurrence_if_due, complete_occurrence, skip_occurrence,
)


def test_compute_next_occurrence_weekly(sample_chore):
    sample_chore.recurrence_type = "weekly"
    next_date = compute_next_occurrence(sample_chore, from_date=date(2026, 1, 1))
    assert next_date == date(2026, 1, 8)


def test_compute_next_occurrence_specific_day_of_month(sample_chore):
    sample_chore.recurrence_type = "specific_day_of_month"
    sample_chore.recurrence_config = {"day_of_month": 15}
    next_date = compute_next_occurrence(sample_chore, from_date=date(2026, 1, 1))
    assert next_date == date(2026, 1, 15)
    # If we're already past the 15th, it should roll to next month.
    next_date2 = compute_next_occurrence(sample_chore, from_date=date(2026, 1, 20))
    assert next_date2 == date(2026, 2, 15)


def test_one_time_chore_has_no_next_occurrence(sample_chore):
    sample_chore.recurrence_type = "one_time"
    assert compute_next_occurrence(sample_chore) is None


def test_generate_occurrence_if_due_creates_pending_occurrence(db, sample_chore):
    occurrence = generate_occurrence_if_due(sample_chore, today=sample_chore.due_date)
    db.session.commit()

    assert occurrence is not None
    assert occurrence.status == "pending"
    assert ChoreOccurrence.query.filter_by(chore_id=sample_chore.id).count() == 1


def test_generate_occurrence_is_idempotent_for_same_date(db, sample_chore):
    due_date = sample_chore.due_date
    first = generate_occurrence_if_due(sample_chore, today=due_date)
    db.session.commit()

    # Simulate a second generation pass being triggered for the same due date
    # before anything else has moved the schedule forward (e.g. a retried
    # cron run) — it must find the existing occurrence, not duplicate it.
    sample_chore.next_scheduled_at = due_date
    second = generate_occurrence_if_due(sample_chore, today=due_date)
    db.session.commit()

    assert first.id == second.id
    assert ChoreOccurrence.query.filter_by(chore_id=sample_chore.id).count() == 1


def test_completing_occurrence_preserves_history_and_schedules_next(db, sample_chore, employee_user):
    occurrence = generate_occurrence_if_due(sample_chore, today=sample_chore.due_date)
    db.session.commit()

    complete_occurrence(occurrence, employee_user, actual_duration_minutes=30, notes="Done")
    db.session.commit()

    assert occurrence.status == "completed"
    assert occurrence.completed_by_id == employee_user.id
    # The completion record itself is never overwritten by later occurrences.
    assert db.session.get(ChoreOccurrence, occurrence.id).status == "completed"
    assert sample_chore.next_scheduled_at > sample_chore.due_date


def test_skip_occurrence_records_reason_without_deleting_it(db, sample_chore, employee_user):
    occurrence = generate_occurrence_if_due(sample_chore, today=sample_chore.due_date)
    db.session.commit()

    skip_occurrence(occurrence, employee_user, "On PTO this week")
    db.session.commit()

    assert occurrence.status == "skipped"
    assert occurrence.skip_reason == "On PTO this week"
    assert db.session.get(ChoreOccurrence, occurrence.id) is not None

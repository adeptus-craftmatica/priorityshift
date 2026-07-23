from datetime import date, timedelta

from app.services.deadline_service import get_projected_completion


def test_insufficient_data_without_estimated_hours(sample_project):
    result = get_projected_completion(sample_project)
    assert result["insufficient_data"] is True


def test_projects_completion_from_remaining_effort_and_capacity(db, sample_project, employee_user):
    sample_project.estimated_effort_hours = 40
    sample_project.percent_complete = 50
    sample_project.date_started = date.today() - timedelta(days=14)
    sample_project.total_interruption_minutes = 0
    db.session.commit()

    result = get_projected_completion(sample_project)

    assert result["insufficient_data"] is False
    assert result["remaining_hours"] == 20
    assert result["effective_hours_per_week"] == employee_user.capacity_hours_per_week
    assert result["projected_completion"] is not None


def test_interruption_drag_slows_the_projection(db, sample_project):
    sample_project.estimated_effort_hours = 40
    sample_project.percent_complete = 0
    sample_project.date_started = date.today() - timedelta(days=7)
    sample_project.total_interruption_minutes = 60 * 20  # 20 hours lost this week
    db.session.commit()

    result = get_projected_completion(sample_project)

    assert result["interruption_hours_per_week"] == 20
    assert result["effective_hours_per_week"] < 40


def test_already_complete_projects_finish_today(db, sample_project):
    sample_project.estimated_effort_hours = 40
    sample_project.percent_complete = 100
    db.session.commit()

    result = get_projected_completion(sample_project)

    assert result["projected_completion"] == date.today()
    assert result["at_risk"] is False


def test_unassigned_project_is_insufficient_data(db, sample_project):
    sample_project.estimated_effort_hours = 40
    sample_project.assignments = []
    sample_project.owner_id = None
    db.session.commit()

    result = get_projected_completion(sample_project)

    assert result["insufficient_data"] is True

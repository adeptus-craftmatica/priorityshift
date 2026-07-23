from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import Interruption
from app.services.forecast_service import get_developer_forecast, get_org_forecast


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


def test_forecast_spreads_remaining_hours_across_weeks_until_deadline(db, employee_user, sample_project):
    sample_project.estimated_effort_hours = 40
    sample_project.percent_complete = 0
    sample_project.target_deadline = date.today() + timedelta(weeks=2)
    sample_project.revised_deadline = None
    db.session.commit()

    forecast = get_developer_forecast(employee_user, weeks_ahead=8)

    # 40h remaining over ~2 weeks -> ~20h/week, only in the first 2 weekly buckets.
    assert forecast["weeks"][0]["project_hours"] == 20.0
    assert forecast["weeks"][1]["project_hours"] == 20.0
    assert forecast["weeks"][2]["project_hours"] == 0.0


def test_forecast_flags_overloaded_weeks(db, employee_user, sample_project):
    sample_project.estimated_effort_hours = 200
    sample_project.percent_complete = 0
    sample_project.target_deadline = date.today() + timedelta(weeks=1)
    sample_project.revised_deadline = None
    db.session.commit()

    forecast = get_developer_forecast(employee_user, weeks_ahead=4)

    assert forecast["weeks"][0]["overloaded"] is True
    assert forecast["overloaded_week_count"] >= 1


def test_forecast_reduces_effective_capacity_from_recent_interruptions(db, employee_user):
    db.session.add(Interruption(
        user_id=employee_user.id, duration_minutes=600, context_switch_minutes=60,
        start_time=datetime.now() - timedelta(days=3),
    ))
    db.session.commit()

    forecast = get_developer_forecast(employee_user, weeks_ahead=4)

    assert forecast["interruption_hours_per_week"] > 0
    assert forecast["effective_capacity_per_week"] < employee_user.capacity_hours_per_week


def test_forecast_with_no_committed_work_has_zero_backlog(db, employee_user):
    forecast = get_developer_forecast(employee_user, weeks_ahead=4)
    assert forecast["weeks_of_backlog"] == 0.0
    assert forecast["overloaded_week_count"] == 0


def test_org_forecast_aggregates_across_active_users(db, employee_user, manager_user, sample_project):
    sample_project.estimated_effort_hours = 40
    sample_project.percent_complete = 0
    db.session.commit()

    data = get_org_forecast(weeks_ahead=4)

    assert len(data["developer_forecasts"]) >= 2
    assert len(data["org_weeks"]) == 4
    assert data["org_weeks"][0]["total_hours"] >= 0


def test_workload_forecast_route_requires_permission(client, employee_user):
    login(client, "employee1")
    resp = client.get("/reports/workload-forecast")
    assert resp.status_code == 403


def test_workload_forecast_route_renders_for_director(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/workload-forecast")
    assert resp.status_code == 200


def test_workload_forecast_csv_export(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/workload-forecast?export=csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"

from datetime import date

from app.services.calendar_service import get_month_grid


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


def test_month_grid_places_project_deadline_on_the_right_day(sample_project):
    deadline = sample_project.target_deadline
    data = get_month_grid(deadline.year, deadline.month)

    matches = [d for week in data["weeks"] for d in week if d["date"] == deadline]
    assert len(matches) == 1
    assert sample_project in matches[0]["projects"]


def test_month_grid_places_chore_due_date_on_the_right_day(sample_chore):
    due = sample_chore.next_scheduled_at
    data = get_month_grid(due.year, due.month)

    matches = [d for week in data["weeks"] for d in week if d["date"] == due]
    assert sample_chore in matches[0]["chores"]


def test_month_grid_is_rectangular_and_marks_today(app):
    today = date.today()
    data = get_month_grid(today.year, today.month)

    assert all(len(week) == 7 for week in data["weeks"])
    todays = [d for week in data["weeks"] for d in week if d["is_today"]]
    assert len(todays) == 1
    assert todays[0]["date"] == today


def test_calendar_route_requires_login(client):
    resp = client.get("/calendar/")
    assert resp.status_code in (302, 401)


def test_calendar_route_renders_for_logged_in_user(client, employee_user):
    login(client, "employee1")
    resp = client.get("/calendar/")
    assert resp.status_code == 200

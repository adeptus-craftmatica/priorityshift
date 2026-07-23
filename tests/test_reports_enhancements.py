from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import ChoreOccurrence
from app.services.reports_service import chore_compliance_report, workload_report


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


def test_workload_report_includes_capacity_utilization(db, employee_user, sample_project):
    sample_project.estimated_effort_hours = 20
    sample_project.percent_complete = 0
    db.session.commit()

    data = workload_report()

    row = next(r for r in data["capacity_utilization"] if r["user"].id == employee_user.id)
    assert row["committed_hours"] == 20
    assert row["utilization_pct"] == round(20 / employee_user.capacity_hours_per_week * 100)


def test_chore_compliance_report_buckets_occurrences(db, sample_chore):
    today = date.today()
    db.session.add_all([
        ChoreOccurrence(chore_id=sample_chore.id, occurrence_date=today - timedelta(days=3),
                        status="completed", completed_at=datetime.combine(today - timedelta(days=4), datetime.min.time())),
        ChoreOccurrence(chore_id=sample_chore.id, occurrence_date=today - timedelta(days=2),
                        status="completed", completed_at=datetime.combine(today, datetime.min.time())),
        ChoreOccurrence(chore_id=sample_chore.id, occurrence_date=today - timedelta(days=1),
                        status="pending"),
    ])
    db.session.commit()

    data = chore_compliance_report()

    assert data["on_time_count"] == 1
    assert data["late_count"] == 1
    assert data["missed_count"] == 1
    assert data["compliance_rate"] == round(1 / 3 * 100, 1)


def test_chore_compliance_route_requires_export_permission(client, employee_user):
    login(client, "employee1")
    resp = client.get("/reports/chore-compliance")
    assert resp.status_code == 403


def test_chore_compliance_route_renders_for_director(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/chore-compliance")
    assert resp.status_code == 200


def test_chore_compliance_csv_export(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/chore-compliance?export=csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert resp.data.startswith(b"Due Date,Chore,Assignee,Status")


def test_chore_compliance_pdf_export(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/chore-compliance?export=pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"

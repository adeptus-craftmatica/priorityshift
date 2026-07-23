from datetime import date, timedelta

from app.blueprints.projects.routes import _build_timeline_rows


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


class FakePriorityLevel:
    def __init__(self, name):
        self.name = name


class FakeProject:
    def __init__(self, date_started, target_deadline, revised_deadline=None, priority_name="Normal"):
        self.date_started = date_started
        self.date_requested = None
        self.target_deadline = target_deadline
        self.revised_deadline = revised_deadline
        self.priority_level = FakePriorityLevel(priority_name)


def test_timeline_rows_skip_projects_without_dates():
    window_start = date.today()
    window_end = date.today() + timedelta(weeks=8)
    rows = _build_timeline_rows([FakeProject(None, None)], window_start, window_end)
    assert rows == []


def test_timeline_rows_skip_projects_entirely_outside_window():
    window_start = date.today()
    window_end = date.today() + timedelta(weeks=8)
    long_ago = FakeProject(window_start - timedelta(weeks=20), window_start - timedelta(weeks=15))
    rows = _build_timeline_rows([long_ago], window_start, window_end)
    assert rows == []


def test_timeline_rows_positions_project_bar_within_window():
    window_start = date.today()
    window_end = date.today() + timedelta(weeks=8)
    p = FakeProject(window_start, window_start + timedelta(weeks=4))
    rows = _build_timeline_rows([p], window_start, window_end)
    assert len(rows) == 1
    assert rows[0]["left_pct"] == 0.0
    assert rows[0]["width_pct"] == 50.0


def test_timeline_rows_prefers_revised_deadline_over_target(app):
    window_start = date.today()
    window_end = date.today() + timedelta(weeks=8)
    p = FakeProject(window_start, window_start + timedelta(weeks=1), revised_deadline=window_start + timedelta(weeks=4))
    rows = _build_timeline_rows([p], window_start, window_end)
    assert rows[0]["width_pct"] == 50.0


def test_board_view_groups_projects_by_phase(client, manager_user, sample_project):
    login(client, "manager1")
    resp = client.get("/projects/?view=board")
    assert resp.status_code == 200
    assert b"kanban-board" in resp.data
    assert sample_project.title.encode() in resp.data


def test_timeline_view_renders(client, manager_user, sample_project):
    login(client, "manager1")
    resp = client.get("/projects/?view=timeline")
    assert resp.status_code == 200


def test_phase_ajax_updates_project_and_returns_json(client, db, manager_user, sample_project, phases):
    login(client, "manager1")
    other_phase = phases["Completed"]
    resp = client.post(f"/projects/{sample_project.id}/phase-ajax", data={"phase_id": other_phase.id})
    assert resp.status_code == 200
    assert resp.json["success"] is True
    db.session.refresh(sample_project)
    assert sample_project.phase_id == other_phase.id


def test_phase_ajax_requires_login(client, sample_project):
    resp = client.post(f"/projects/{sample_project.id}/phase-ajax", data={"phase_id": 1})
    assert resp.status_code in (302, 401)

from app.extensions import db
from app.models import ActivityLog
from app.services.user_lifecycle import archive_user, get_user_history, set_active, unarchive_user


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


# ---------- Service-level ----------

def test_set_active_flips_state_and_logs(db, employee_user):
    set_active(employee_user, False)
    db.session.commit()
    assert employee_user.active is False
    history = get_user_history(employee_user)
    assert len(history) == 1
    assert history[0].event_type == "locked"


def test_set_active_is_a_noop_when_state_already_matches(db, employee_user):
    result = set_active(employee_user, True)  # already active
    assert result is None
    assert get_user_history(employee_user) == []


def test_archive_user_sets_both_flags_and_logs(db, employee_user):
    archive_user(employee_user, reason="left the company")
    db.session.commit()
    assert employee_user.is_archived is True
    assert employee_user.active is False
    history = get_user_history(employee_user)
    assert len(history) == 1
    assert history[0].event_type == "archived"
    assert "left the company" in history[0].description


def test_unarchive_user_restores_access_and_logs(db, employee_user):
    archive_user(employee_user)
    db.session.commit()
    unarchive_user(employee_user)
    db.session.commit()
    assert employee_user.is_archived is False
    assert employee_user.active is True
    history = get_user_history(employee_user)
    assert [h.event_type for h in history] == ["unarchived", "archived"]


def test_archive_is_a_noop_when_already_archived(db, employee_user):
    archive_user(employee_user)
    db.session.commit()
    result = archive_user(employee_user)
    assert result is None


def test_history_is_never_deleted_across_multiple_transitions(db, employee_user):
    set_active(employee_user, False)
    db.session.commit()
    set_active(employee_user, True)
    db.session.commit()
    archive_user(employee_user)
    db.session.commit()
    unarchive_user(employee_user)
    db.session.commit()

    history = get_user_history(employee_user)
    assert [h.event_type for h in history] == ["unarchived", "archived", "unlocked", "locked"]


# ---------- Web routes ----------

def test_archive_route_requires_permission(client, employee_user, manager_user):
    login(client, "employee1")
    resp = client.post(f"/admin/users/{manager_user.id}/archive")
    assert resp.status_code == 403


def test_archive_route_works_for_director(client, director_user, employee_user):
    login(client, "director1")
    resp = client.post(f"/admin/users/{employee_user.id}/archive")
    assert resp.status_code == 302
    db.session.refresh(employee_user)
    assert employee_user.is_archived is True
    assert employee_user.active is False


def test_archived_users_hidden_by_default_from_users_list(client, director_user, employee_user):
    # employee_user's name also appears in the (unfiltered) manager/team-lead
    # dropdown choices, so check the "Archived" status badge specifically
    # rather than searching the whole page for their name.
    login(client, "director1")
    client.post(f"/admin/users/{employee_user.id}/archive")
    resp = client.get("/admin/users")
    assert b">Archived<" not in resp.data

    resp_shown = client.get("/admin/users?show_archived=1")
    assert b">Archived<" in resp_shown.data


def test_cannot_archive_own_account(client, director_user):
    login(client, "director1")
    resp = client.post(f"/admin/users/{director_user.id}/archive", follow_redirects=True)
    db.session.refresh(director_user)
    assert director_user.is_archived is False


def test_unarchive_route_works(client, director_user, employee_user):
    login(client, "director1")
    client.post(f"/admin/users/{employee_user.id}/archive")
    resp = client.post(f"/admin/users/{employee_user.id}/unarchive")
    assert resp.status_code == 302
    db.session.refresh(employee_user)
    assert employee_user.is_archived is False
    assert employee_user.active is True


def test_user_history_route_shows_events(client, director_user, employee_user):
    login(client, "director1")
    client.post(f"/admin/users/{employee_user.id}/archive")
    resp = client.get(f"/admin/users/{employee_user.id}/history")
    assert resp.status_code == 200
    assert b"archived" in resp.data.lower()


def test_toggle_active_route_logs_activity(client, director_user, employee_user):
    login(client, "director1")
    client.post(f"/admin/users/{employee_user.id}/toggle-active")
    entries = ActivityLog.query.filter_by(item_type="user", item_id=employee_user.id).all()
    assert len(entries) == 1
    assert entries[0].event_type == "locked"
    assert entries[0].actor_id == director_user.id


def test_editing_active_checkbox_in_user_form_is_also_logged(client, director_user, employee_user):
    login(client, "director1")
    resp = client.post("/admin/users", data={
        "id": employee_user.id,
        "username": employee_user.username,
        "email": employee_user.email,
        "full_name": employee_user.full_name,
        "password": "",
        "role_id": employee_user.role_id,
        "manager_id": 0,
        "team_lead_id": 0,
        "department_ids": [],
        "team_ids": [],
        "capacity_hours_per_week": 40,
        "client_id": 0,
        # active checkbox omitted == unchecked -> False
    })
    assert resp.status_code == 302
    entries = ActivityLog.query.filter_by(item_type="user", item_id=employee_user.id).all()
    assert len(entries) == 1
    assert entries[0].event_type == "locked"

from flask import g

from app.models import User


def _drop_cached_login():
    """Our test fixtures hold one Flask app context open for the whole
    test function, so Flask reuses it across every test-client call
    instead of pushing a fresh one per request. Flask-Login caches the
    resolved user on that shared `g`, so switching which logged-in client
    makes the next request needs this — otherwise `current_user` silently
    stays whoever was resolved first, regardless of whose session cookie
    is actually being sent. This is purely a test-harness artifact: real
    HTTP requests each get their own app context, so production code never
    hits this."""
    if hasattr(g, "_login_user"):
        del g._login_user


def login(client, username, password="testpass123"):
    return client.post("/auth/login", data={"username": username, "password": password})


def test_admin_can_reset_another_users_password(client, db, director_user, employee_user):
    login(client, "director1")

    resp = client.post(
        f"/admin/users/{employee_user.id}/reset-password",
        data={"password": "brandnewpass", "confirm_password": "brandnewpass"},
    )
    assert resp.status_code == 302

    refreshed = db.session.get(User, employee_user.id)
    assert refreshed.check_password("brandnewpass")
    assert not refreshed.check_password("testpass123")


def test_reset_password_requires_matching_confirmation(client, director_user, employee_user):
    login(client, "director1")

    resp = client.post(
        f"/admin/users/{employee_user.id}/reset-password",
        data={"password": "brandnewpass", "confirm_password": "somethingelse"},
    )
    assert resp.status_code == 200  # re-renders the form with a validation error
    assert b"must match" in resp.data


def test_employee_cannot_reset_passwords(client, employee_user):
    login(client, "employee1")
    resp = client.get(f"/admin/users/{employee_user.id}/reset-password")
    assert resp.status_code == 403


def test_admin_can_lock_out_another_user(client, db, director_user, employee_user):
    login(client, "director1")

    resp = client.post(f"/admin/users/{employee_user.id}/toggle-active")
    assert resp.status_code == 302

    refreshed = db.session.get(User, employee_user.id)
    assert refreshed.active is False


def test_locked_out_user_cannot_log_in(client, db, director_user, employee_user):
    login(client, "director1")
    client.post(f"/admin/users/{employee_user.id}/toggle-active")
    client.post("/auth/logout")

    resp = login(client, "employee1")
    resp = client.get("/dashboard/", follow_redirects=True)
    # Should have been bounced back to login, not let in.
    assert b"Sign in" in resp.data


def test_locking_out_invalidates_an_existing_session_immediately(client, db, director_user, employee_user):
    # Employee logs in first and can reach their dashboard.
    login(client, "employee1")
    resp = client.get("/dashboard/")
    assert resp.status_code == 200

    # A director locks them out in a *separate* client (simulating another
    # browser/session) while the employee's session cookie is still valid.
    _drop_cached_login()
    admin_client = client.application.test_client()
    admin_client.post("/auth/login", data={"username": "director1", "password": "testpass123"})
    toggle_resp = admin_client.post(f"/admin/users/{employee_user.id}/toggle-active")
    assert toggle_resp.status_code == 302

    refreshed = db.session.get(User, employee_user.id)
    assert refreshed.active is False

    # The employee's existing session must stop working on their very next
    # request — not just block future logins.
    _drop_cached_login()
    resp = client.get("/dashboard/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_admin_cannot_lock_out_their_own_account(client, db, director_user):
    login(client, "director1")

    resp = client.post(f"/admin/users/{director_user.id}/toggle-active", follow_redirects=True)
    assert resp.status_code == 200

    refreshed = db.session.get(User, director_user.id)
    assert refreshed.active is True


def test_unlocking_restores_login(client, db, director_user, employee_user):
    login(client, "director1")
    client.post(f"/admin/users/{employee_user.id}/toggle-active")  # lock
    client.post(f"/admin/users/{employee_user.id}/toggle-active")  # unlock
    client.post("/auth/logout")

    resp = login(client, "employee1")
    assert resp.status_code == 302
    assert "/dashboard/" in resp.headers["Location"]

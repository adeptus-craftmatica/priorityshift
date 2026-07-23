from datetime import date, timedelta

from app.models import Client, Comment, Project


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


def make_client_contact(db, roles, acme, username="contact1"):
    from tests.conftest import make_user
    user = make_user(db, roles, "employee", username)
    user.client_id = acme.id
    db.session.commit()
    return user


def make_acme_project(db, priority_levels, phases, acme, manager_user, employee_user, title="Acme Redesign"):
    project = Project(
        project_number=f"PRJ-{title[:4].upper()}", title=title,
        priority_level_id=priority_levels["High"].id, original_priority_level_id=priority_levels["High"].id,
        phase_id=phases["Development"].id, owner_id=manager_user.id, client_id=acme.id,
        target_deadline=date.today() + timedelta(days=10), original_deadline=date.today() + timedelta(days=10),
        percent_complete=42,
    )
    db.session.add(project)
    db.session.commit()
    return project


def test_client_contact_dashboard_only_shows_their_own_client_projects(db, roles, priority_levels, phases, manager_user, employee_user, client):
    acme = Client(name="Acme Co")
    globex = Client(name="Globex Co")
    db.session.add_all([acme, globex])
    db.session.commit()

    make_acme_project(db, priority_levels, phases, acme, manager_user, employee_user, title="Acme One")
    make_acme_project(db, priority_levels, phases, globex, manager_user, employee_user, title="Globex One")
    contact = make_client_contact(db, roles, acme)

    login(client, "contact1")
    resp = client.get("/portal/")
    assert resp.status_code == 200
    assert b"Acme One" in resp.data
    assert b"Globex One" not in resp.data


def test_client_contact_cannot_view_another_clients_project(db, roles, priority_levels, phases, manager_user, employee_user, client):
    acme = Client(name="Acme Co")
    globex = Client(name="Globex Co")
    db.session.add_all([acme, globex])
    db.session.commit()

    other_project = make_acme_project(db, priority_levels, phases, globex, manager_user, employee_user, title="Globex Secret")
    make_client_contact(db, roles, acme)

    login(client, "contact1")
    resp = client.get(f"/portal/projects/{other_project.id}")
    assert resp.status_code == 404


def test_client_contact_is_redirected_away_from_internal_app(db, roles, priority_levels, phases, manager_user, employee_user, client):
    acme = Client(name="Acme Co")
    db.session.add(acme)
    db.session.commit()
    make_client_contact(db, roles, acme)

    login(client, "contact1")
    resp = client.get("/projects/")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/portal/")


def test_normal_employee_is_not_redirected_to_portal(client, employee_user):
    login(client, "employee1")
    resp = client.get("/projects/")
    assert resp.status_code == 200


def test_client_contact_can_post_a_client_visible_comment(db, roles, priority_levels, phases, manager_user, employee_user, client):
    acme = Client(name="Acme Co")
    db.session.add(acme)
    db.session.commit()
    project = make_acme_project(db, priority_levels, phases, acme, manager_user, employee_user)
    make_client_contact(db, roles, acme)

    login(client, "contact1")
    resp = client.post(f"/portal/projects/{project.id}/comments", data={"body": "How's it going?"})
    assert resp.status_code == 302

    comment = Comment.query.filter_by(item_type="project", item_id=project.id).first()
    assert comment is not None
    assert comment.client_visible is True
    assert comment.body == "How's it going?"


def test_internal_comment_is_not_visible_in_portal(db, roles, priority_levels, phases, manager_user, employee_user, client):
    acme = Client(name="Acme Co")
    db.session.add(acme)
    db.session.commit()
    project = make_acme_project(db, priority_levels, phases, acme, manager_user, employee_user)
    make_client_contact(db, roles, acme)

    internal_comment = Comment(
        item_type="project", item_id=project.id, author_id=manager_user.id,
        body="Internal risk assessment — do not share.", client_visible=False,
    )
    db.session.add(internal_comment)
    db.session.commit()

    login(client, "contact1")
    resp = client.get(f"/portal/projects/{project.id}")
    assert b"Internal risk assessment" not in resp.data

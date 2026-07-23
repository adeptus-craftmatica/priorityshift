def login(client, username):
    client.post("/auth/login", data={"username": username, "password": "testpass123"})


def test_employee_cannot_create_project(client, employee_user):
    login(client, "employee1")
    resp = client.get("/projects/new")
    assert resp.status_code == 403


def test_manager_can_create_project(client, manager_user):
    login(client, "manager1")
    resp = client.get("/projects/new")
    assert resp.status_code == 200


def test_employee_cannot_view_org_dashboard(client, employee_user):
    login(client, "employee1")
    resp = client.get("/dashboard/organization")
    assert resp.status_code == 403


def test_director_can_view_org_dashboard(client, director_user):
    login(client, "director1")
    resp = client.get("/dashboard/organization")
    assert resp.status_code == 200


def test_manager_cannot_manage_roles(client, manager_user):
    login(client, "manager1")
    resp = client.get("/admin/roles")
    assert resp.status_code == 403


def test_director_can_manage_roles(client, director_user):
    login(client, "director1")
    resp = client.get("/admin/roles")
    assert resp.status_code == 200

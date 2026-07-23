def test_login_page_loads(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert b"Sign in" in resp.data


def test_login_success_redirects_to_dashboard(client, employee_user):
    resp = client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    assert resp.status_code == 302
    assert "/dashboard/" in resp.headers["Location"]


def test_login_wrong_password_fails(client, employee_user):
    resp = client.post("/auth/login", data={"username": "employee1", "password": "wrong"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"isn&#39;t right" in resp.data or b"isn't right" in resp.data


def test_dashboard_requires_login(client):
    resp = client.get("/dashboard/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_logout(client, employee_user):
    client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    resp = client.post("/auth/logout")
    assert resp.status_code == 302
    resp = client.get("/dashboard/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]

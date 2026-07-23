def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


def test_priority_changes_csv_export(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/priority-changes?export=csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert resp.data.startswith(b"Date,Type,Item ID")


def test_priority_changes_excel_export(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/priority-changes?export=xlsx")
    assert resp.status_code == 200
    assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(resp.data) > 0


def test_priority_changes_pdf_export(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/priority-changes?export=pdf")
    assert resp.status_code == 200
    assert resp.mimetype == "application/pdf"
    assert resp.data.startswith(b"%PDF-")


def test_workload_report_requires_export_permission(client, employee_user):
    login(client, "employee1")
    resp = client.get("/reports/workload?export=pdf")
    assert resp.status_code == 403


def test_workload_pdf_export_for_permitted_user(client, director_user):
    login(client, "director1")
    resp = client.get("/reports/workload?export=pdf")
    assert resp.status_code == 200
    assert resp.data.startswith(b"%PDF-")

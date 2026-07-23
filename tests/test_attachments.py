import io

from app.models import ActivityLog, Attachment


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


def _upload(client, project_id, filename="notes.txt", content=b"hello world"):
    return client.post(
        f"/attachments/project/{project_id}",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def test_upload_creates_attachment_and_activity_log(client, db, employee_user, sample_project):
    login(client, "employee1")
    resp = _upload(client, sample_project.id)
    assert resp.status_code == 302

    attachment = Attachment.query.filter_by(item_type="project", item_id=sample_project.id).first()
    assert attachment is not None
    assert attachment.filename == "notes.txt"
    assert attachment.uploaded_by_id == employee_user.id

    log = ActivityLog.query.filter_by(item_type="project", item_id=sample_project.id, event_type="file_uploaded").first()
    assert log is not None


def test_upload_rejects_disallowed_extension(client, db, employee_user, sample_project):
    login(client, "employee1")
    resp = _upload(client, sample_project.id, filename="virus.exe", content=b"nope")
    assert resp.status_code == 302

    assert Attachment.query.filter_by(item_type="project", item_id=sample_project.id).count() == 0


def test_download_returns_uploaded_content(client, db, employee_user, sample_project):
    login(client, "employee1")
    _upload(client, sample_project.id, content=b"the actual file content")
    attachment = Attachment.query.filter_by(item_type="project", item_id=sample_project.id).first()

    resp = client.get(f"/attachments/download/{attachment.id}")
    assert resp.status_code == 200
    assert resp.data == b"the actual file content"


def test_uploader_can_delete_their_own_attachment(client, db, employee_user, sample_project):
    login(client, "employee1")
    _upload(client, sample_project.id)
    attachment = Attachment.query.filter_by(item_type="project", item_id=sample_project.id).first()

    resp = client.post(f"/attachments/{attachment.id}/delete")
    assert resp.status_code == 302
    assert db.session.get(Attachment, attachment.id) is None


def test_other_non_admin_user_cannot_delete_someone_elses_attachment(client, db, employee_user, manager_user, sample_project):
    login(client, "employee1")
    _upload(client, sample_project.id)
    attachment = Attachment.query.filter_by(item_type="project", item_id=sample_project.id).first()
    client.post("/auth/logout")

    login(client, "manager1")
    resp = client.post(f"/attachments/{attachment.id}/delete")
    assert resp.status_code == 403
    assert db.session.get(Attachment, attachment.id) is not None

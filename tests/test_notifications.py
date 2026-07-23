from datetime import date, timedelta

from app.models import DeadlineRevision, Notification, Project, ProjectAssignment


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


def test_assigning_a_developer_notifies_them(client, db, manager_user, employee_user, priority_levels, phases):
    project = Project(
        project_number="PRJ-9001", title="Notify Me Project", priority_level_id=priority_levels["Normal"].id,
        original_priority_level_id=priority_levels["Normal"].id, phase_id=phases["Development"].id,
    )
    db.session.add(project)
    db.session.commit()

    login(client, "manager1")
    resp = client.post(
        f"/projects/{project.id}/edit",
        data={
            "title": project.title, "category": "standard", "phase_id": phases["Development"].id,
            "client_id": 0, "requesting_department_id": 0, "owner_id": 0, "approving_manager_id": 0,
            "assignee_ids": [employee_user.id], "percent_complete": 0,
        },
    )
    assert resp.status_code == 302

    notification = Notification.query.filter_by(user_id=employee_user.id, type="assignment").first()
    assert notification is not None
    assert "Notify Me Project" in notification.title


def test_manual_deadline_edit_creates_revision_and_notifies_assignees(client, db, manager_user, employee_user, sample_project):
    original_deadline = sample_project.target_deadline
    new_deadline = original_deadline + timedelta(days=10)

    login(client, "manager1")
    resp = client.post(
        f"/projects/{sample_project.id}/edit",
        data={
            "title": sample_project.title, "category": "standard", "phase_id": sample_project.phase_id,
            "client_id": 0, "requesting_department_id": 0, "owner_id": 0, "approving_manager_id": 0,
            "assignee_ids": [employee_user.id], "percent_complete": 0,
            "target_deadline": new_deadline.isoformat(),
        },
    )
    assert resp.status_code == 302

    refreshed = db.session.get(Project, sample_project.id)
    assert refreshed.target_deadline == new_deadline
    # The core bug being fixed: this must be tracked, not silently overwritten.
    revision = DeadlineRevision.query.filter_by(project_id=sample_project.id).first()
    assert revision is not None
    assert revision.new_deadline == new_deadline

    notification = Notification.query.filter_by(user_id=employee_user.id, type="deadline_change").first()
    assert notification is not None


def test_assigning_over_capacity_notifies_the_assigner(client, db, manager_user, employee_user, priority_levels, phases):
    employee_user.capacity_hours_per_week = 5
    db.session.commit()

    project = Project(
        project_number="PRJ-9002", title="Heavy Project", priority_level_id=priority_levels["Normal"].id,
        original_priority_level_id=priority_levels["Normal"].id, phase_id=phases["Development"].id,
        estimated_effort_hours=40, percent_complete=0,
    )
    db.session.add(project)
    db.session.commit()

    login(client, "manager1")
    client.post(
        f"/projects/{project.id}/edit",
        data={
            "title": project.title, "category": "standard", "phase_id": phases["Development"].id,
            "client_id": 0, "requesting_department_id": 0, "owner_id": 0, "approving_manager_id": 0,
            "assignee_ids": [employee_user.id], "percent_complete": 0,
        },
    )

    conflict = Notification.query.filter_by(user_id=manager_user.id, type="capacity_conflict").first()
    assert conflict is not None
    assert "over capacity" in conflict.title


def test_comment_mention_notifies_the_mentioned_user(client, db, manager_user, employee_user, sample_project):
    login(client, "manager1")
    resp = client.post(
        f"/comments/project/{sample_project.id}",
        data={"body": f"Hey @{employee_user.username}, can you take a look?"},
    )
    assert resp.status_code == 200

    notification = Notification.query.filter_by(user_id=employee_user.id, type="comment_mention").first()
    assert notification is not None


def test_decision_comment_notifies_assignees(client, db, manager_user, employee_user, sample_project):
    login(client, "manager1")
    client.post(
        f"/comments/project/{sample_project.id}",
        data={"body": "We're going with option B.", "is_decision": "y"},
    )

    notification = Notification.query.filter_by(user_id=employee_user.id, type="decision").first()
    assert notification is not None


def test_chore_reassignment_notifies_new_assignee(client, db, director_user, employee_user, manager_user, sample_chore):
    login(client, "director1")
    from app.services.chore_service import generate_occurrence_if_due
    occurrence = generate_occurrence_if_due(sample_chore, today=sample_chore.due_date)
    db.session.commit()

    resp = client.post(
        f"/chores/occurrences/{occurrence.id}/reassign",
        data={"new_user_id": manager_user.id},
    )
    assert resp.status_code == 302

    notification = Notification.query.filter_by(user_id=manager_user.id, type="assignment").first()
    assert notification is not None


def test_due_reminders_are_deduplicated_on_repeated_dashboard_loads(client, db, employee_user, priority_levels, phases):
    project = Project(
        project_number="PRJ-9003", title="Overdue Project", priority_level_id=priority_levels["Normal"].id,
        original_priority_level_id=priority_levels["Normal"].id, phase_id=phases["Development"].id,
        target_deadline=date.today() - timedelta(days=2),
    )
    db.session.add(project)
    db.session.commit()
    db.session.add(ProjectAssignment(project_id=project.id, user_id=employee_user.id))
    db.session.commit()

    login(client, "employee1")
    client.get("/dashboard/")
    client.get("/dashboard/")  # loading twice must not double the reminder

    overdue_notifications = Notification.query.filter_by(user_id=employee_user.id, type="overdue", item_id=project.id).all()
    assert len(overdue_notifications) == 1

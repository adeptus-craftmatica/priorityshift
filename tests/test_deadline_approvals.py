from datetime import date, timedelta

from app.extensions import db
from app.models import DeadlineRevision, WorkflowRule
from app.services.deadline_service import (
    approve_deadline_revision, deadline_push_requires_approval,
    reject_deadline_revision, revise_deadline,
)


def login(client, username, password="testpass123"):
    client.post("/auth/login", data={"username": username, "password": password})


def make_rule(db, threshold=5):
    rule = WorkflowRule(rule_type="require_approval_for_deadline_push", threshold=threshold, active=True)
    db.session.add(rule)
    db.session.commit()
    return rule


def test_no_approval_needed_without_an_active_rule(db, sample_project, manager_user):
    previous = sample_project.target_deadline
    needs_approval = deadline_push_requires_approval(sample_project, previous, previous + timedelta(days=30), manager_user)
    assert needs_approval is False


def test_small_push_does_not_need_approval(db, sample_project, manager_user):
    make_rule(db, threshold=5)
    previous = sample_project.target_deadline
    needs_approval = deadline_push_requires_approval(sample_project, previous, previous + timedelta(days=3), manager_user)
    assert needs_approval is False


def test_large_push_needs_approval_for_unprivileged_requester(db, sample_project, manager_user):
    make_rule(db, threshold=5)
    previous = sample_project.target_deadline
    needs_approval = deadline_push_requires_approval(sample_project, previous, previous + timedelta(days=10), manager_user)
    assert needs_approval is True


def test_privileged_requester_bypasses_approval(db, sample_project, director_user):
    make_rule(db, threshold=5)
    previous = sample_project.target_deadline
    needs_approval = deadline_push_requires_approval(sample_project, previous, previous + timedelta(days=10), director_user)
    assert needs_approval is False


def test_revise_deadline_creates_pending_revision_without_touching_project(db, sample_project, manager_user):
    make_rule(db, threshold=5)
    original_deadline = sample_project.target_deadline
    new_deadline = original_deadline + timedelta(days=10)

    revision = revise_deadline(sample_project, new_deadline, reason="big push", changed_by=manager_user)
    db.session.commit()

    assert revision.status == "pending"
    assert sample_project.target_deadline == original_deadline


def test_approving_a_pending_revision_applies_it(db, sample_project, manager_user, director_user):
    make_rule(db, threshold=5)
    original_deadline = sample_project.target_deadline
    new_deadline = original_deadline + timedelta(days=10)

    revision = revise_deadline(sample_project, new_deadline, reason="big push", changed_by=manager_user)
    db.session.commit()

    approve_deadline_revision(revision, director_user, notes="looks fine")
    db.session.commit()

    assert revision.status == "approved"
    assert sample_project.target_deadline == new_deadline
    assert sample_project.revised_deadline == new_deadline


def test_rejecting_a_pending_revision_leaves_project_untouched(db, sample_project, manager_user, director_user):
    make_rule(db, threshold=5)
    original_deadline = sample_project.target_deadline
    new_deadline = original_deadline + timedelta(days=10)

    revision = revise_deadline(sample_project, new_deadline, reason="big push", changed_by=manager_user)
    db.session.commit()

    reject_deadline_revision(revision, director_user, notes="not justified")
    db.session.commit()

    assert revision.status == "rejected"
    assert sample_project.target_deadline == original_deadline


def test_approval_queue_route_requires_permission(client, employee_user):
    login(client, "employee1")
    resp = client.get("/deadline-approvals/")
    assert resp.status_code == 403


def test_approval_queue_route_renders_for_director(client, director_user):
    login(client, "director1")
    resp = client.get("/deadline-approvals/")
    assert resp.status_code == 200


def test_approve_route_applies_change(client, db, sample_project, manager_user, director_user):
    make_rule(db, threshold=5)
    original_deadline = sample_project.target_deadline
    new_deadline = original_deadline + timedelta(days=10)
    revision = revise_deadline(sample_project, new_deadline, reason="big push", changed_by=manager_user)
    db.session.commit()

    login(client, "director1")
    resp = client.post(f"/deadline-approvals/{revision.id}/approve", data={"decision_notes": "ok"})
    assert resp.status_code == 302

    db.session.refresh(revision)
    db.session.refresh(sample_project)
    assert revision.status == "approved"
    assert sample_project.target_deadline == new_deadline


def test_project_edit_route_defers_large_deadline_push(client, db, sample_project, manager_user):
    make_rule(db, threshold=5)
    original_deadline = sample_project.target_deadline

    login(client, "manager1")
    resp = client.post(
        f"/projects/{sample_project.id}/edit",
        data={
            "title": sample_project.title,
            "category": "standard",
            "phase_id": sample_project.phase_id,
            "target_deadline": (original_deadline + timedelta(days=10)).isoformat(),
            "percent_complete": 0,
        },
    )
    assert resp.status_code in (200, 302)

    db.session.refresh(sample_project)
    assert sample_project.target_deadline == original_deadline
    pending = DeadlineRevision.query.filter_by(project_id=sample_project.id, status="pending").all()
    assert len(pending) == 1

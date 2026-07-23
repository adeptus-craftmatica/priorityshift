from datetime import date, timedelta

from app.models import PriorityEvent, Project, ProjectAssignment, WorkflowRule
from app.services.priority_service import commit_priority_change, preview_priority_change


def test_commit_priority_change_creates_audit_record(db, sample_project, manager_user, priority_levels):
    original_priority_id = sample_project.priority_level_id
    event, preview = commit_priority_change(
        sample_project, priority_levels["Critical"], manager_user,
        reason="Client escalation", acknowledged=True,
    )

    assert event is not None
    assert event.previous_priority_level_id == original_priority_id
    assert event.new_priority_level_id == priority_levels["Critical"].id
    assert sample_project.priority_level_id == priority_levels["Critical"].id
    # Original priority is preserved separately from the current one.
    assert sample_project.original_priority_level_id == original_priority_id
    assert sample_project.reprioritization_count == 1

    stored = PriorityEvent.query.filter_by(item_type="project", item_id=sample_project.id).first()
    assert stored is not None
    assert stored.reason == "Client escalation"


def test_preview_flags_displaced_work_for_shared_developer(db, priority_levels, phases, manager_user, employee_user):
    project_a = Project(
        project_number="PRJ-2001", title="Project A", priority_level_id=priority_levels["Normal"].id,
        original_priority_level_id=priority_levels["Normal"].id, phase_id=phases["Development"].id,
        target_deadline=date.today() + timedelta(days=5), original_deadline=date.today() + timedelta(days=5),
    )
    project_b = Project(
        project_number="PRJ-2002", title="Project B", priority_level_id=priority_levels["Low"].id,
        original_priority_level_id=priority_levels["Low"].id, phase_id=phases["Development"].id,
        target_deadline=date.today() + timedelta(days=20), original_deadline=date.today() + timedelta(days=20),
    )
    db.session.add_all([project_a, project_b])
    db.session.commit()
    db.session.add(ProjectAssignment(project_id=project_a.id, user_id=employee_user.id))
    db.session.add(ProjectAssignment(project_id=project_b.id, user_id=employee_user.id))
    db.session.commit()

    # Project A is currently the developer's top priority (Normal beats Low).
    preview = preview_priority_change(project_b, priority_levels["Critical"], manager_user)

    assert len(preview["displaced"]) == 1
    assert preview["displaced"][0]["item"]["id"] == project_a.id
    assert preview["displaced"][0]["user"].id == employee_user.id


def test_max_critical_per_developer_blocks_without_override(db, sample_project, priority_levels, manager_user, employee_user, phases):
    db.session.add(WorkflowRule(rule_type="max_critical_per_developer", scope="global", threshold=1, active=True))
    db.session.commit()

    other_project = Project(
        project_number="PRJ-3001", title="Already Critical", priority_level_id=priority_levels["Critical"].id,
        original_priority_level_id=priority_levels["Critical"].id, phase_id=phases["Development"].id,
    )
    db.session.add(other_project)
    db.session.commit()
    db.session.add(ProjectAssignment(project_id=other_project.id, user_id=employee_user.id))
    db.session.commit()

    event, preview = commit_priority_change(
        sample_project, priority_levels["Critical"], manager_user, reason="Urgent", acknowledged=True,
    )

    assert event is None
    assert any(w["level"] == "block" for w in preview["warnings"])
    # Nothing should have changed on the project since the change was blocked.
    assert sample_project.priority_level_id == priority_levels["High"].id


def test_override_blocks_bypasses_workflow_rule(db, sample_project, priority_levels, manager_user, employee_user, phases):
    db.session.add(WorkflowRule(rule_type="max_critical_per_developer", scope="global", threshold=1, active=True))
    db.session.commit()

    other_project = Project(
        project_number="PRJ-3002", title="Already Critical", priority_level_id=priority_levels["Critical"].id,
        original_priority_level_id=priority_levels["Critical"].id, phase_id=phases["Development"].id,
    )
    db.session.add(other_project)
    db.session.commit()
    db.session.add(ProjectAssignment(project_id=other_project.id, user_id=employee_user.id))
    db.session.commit()

    event, _preview = commit_priority_change(
        sample_project, priority_levels["Critical"], manager_user, reason="Urgent",
        acknowledged=True, override_blocks=True,
    )

    assert event is not None
    assert sample_project.priority_level_id == priority_levels["Critical"].id

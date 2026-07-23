from datetime import date, timedelta

from app.models import Project, ProjectAssignment
from app.services.priority_queue import get_priority_queue_for_user, get_top_priority_for_user


def _assign(db, project, user):
    db.session.add(ProjectAssignment(project_id=project.id, user_id=user.id))
    db.session.commit()


def test_top_priority_picks_highest_rank_first(db, priority_levels, phases, employee_user):
    low_project = Project(
        project_number="PRJ-4001", title="Low priority work", priority_level_id=priority_levels["Low"].id,
        original_priority_level_id=priority_levels["Low"].id, phase_id=phases["Development"].id,
        target_deadline=date.today() + timedelta(days=1),
    )
    critical_project = Project(
        project_number="PRJ-4002", title="Critical work", priority_level_id=priority_levels["Critical"].id,
        original_priority_level_id=priority_levels["Critical"].id, phase_id=phases["Development"].id,
        target_deadline=date.today() + timedelta(days=30),
    )
    db.session.add_all([low_project, critical_project])
    db.session.commit()
    _assign(db, low_project, employee_user)
    _assign(db, critical_project, employee_user)

    top = get_top_priority_for_user(employee_user)

    assert top is not None
    assert top["obj"].id == critical_project.id


def test_same_priority_breaks_tie_by_deadline(db, priority_levels, phases, employee_user):
    far = Project(
        project_number="PRJ-5001", title="Due later", priority_level_id=priority_levels["High"].id,
        original_priority_level_id=priority_levels["High"].id, phase_id=phases["Development"].id,
        target_deadline=date.today() + timedelta(days=30),
    )
    soon = Project(
        project_number="PRJ-5002", title="Due sooner", priority_level_id=priority_levels["High"].id,
        original_priority_level_id=priority_levels["High"].id, phase_id=phases["Development"].id,
        target_deadline=date.today() + timedelta(days=2),
    )
    db.session.add_all([far, soon])
    db.session.commit()
    _assign(db, far, employee_user)
    _assign(db, soon, employee_user)

    queue = get_priority_queue_for_user(employee_user)

    assert queue[0]["obj"].id == soon.id
    assert queue[1]["obj"].id == far.id


def test_terminal_phase_projects_excluded_from_queue(db, priority_levels, phases, employee_user):
    done = Project(
        project_number="PRJ-6001", title="Finished work", priority_level_id=priority_levels["Critical"].id,
        original_priority_level_id=priority_levels["Critical"].id, phase_id=phases["Completed"].id,
    )
    db.session.add(done)
    db.session.commit()
    _assign(db, done, employee_user)

    assert get_top_priority_for_user(employee_user) is None

import os
from datetime import date, timedelta

import pytest

from app import create_app
from app.config import Config
from app.extensions import db as _db
from app.models import Chore, Idea, PriorityLevel, Project, ProjectAssignment, ProjectPhase, Role, User


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SERVER_NAME = "localhost"


@pytest.fixture()
def app(tmp_path):
    application = create_app(TestConfig)
    # Otherwise this points at the real project's instance/uploads/ dir —
    # attachment tests would write actual files into the real project.
    application.config["UPLOAD_FOLDER"] = str(tmp_path / "uploads")
    os.makedirs(application.config["UPLOAD_FOLDER"], exist_ok=True)
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app):
    return _db


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def roles(db):
    employee = Role(name="Employee", hierarchy_level=6, permissions=["view_own_dashboard", "comment", "create_idea"])
    manager = Role(name="Manager", hierarchy_level=4, permissions=[
        "view_own_dashboard", "view_team_dashboard", "create_project", "create_chore",
        "assign_work", "change_priority", "comment", "complete_chore",
        "create_idea", "convert_idea", "review_requests",
    ])
    director = Role(name="Director", hierarchy_level=3, permissions=manager.permissions + [
        "view_org_dashboard", "approve_priority_change", "manage_roles", "manage_users", "export_reports",
    ])
    db.session.add_all([employee, manager, director])
    db.session.commit()
    return {"employee": employee, "manager": manager, "director": director}


@pytest.fixture()
def priority_levels(db):
    levels = {}
    for name, rank in [("Critical", 1), ("Urgent", 2), ("High", 3), ("Normal", 4), ("Low", 5), ("Paused", 6)]:
        level = PriorityLevel(name=name, rank=rank)
        db.session.add(level)
        levels[name] = level
    db.session.commit()
    return levels


@pytest.fixture()
def phases(db):
    result = {}
    for name, rank, terminal in [("Development", 1, False), ("Completed", 2, True)]:
        phase = ProjectPhase(name=name, rank=rank, is_terminal=terminal)
        db.session.add(phase)
        result[name] = phase
    db.session.commit()
    return result


def make_user(db, roles, role_key, username):
    user = User(username=username, email=f"{username}@example.com", full_name=username.title(), role_id=roles[role_key].id)
    user.set_password("testpass123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture()
def employee_user(db, roles):
    return make_user(db, roles, "employee", "employee1")


@pytest.fixture()
def manager_user(db, roles):
    return make_user(db, roles, "manager", "manager1")


@pytest.fixture()
def director_user(db, roles):
    return make_user(db, roles, "director", "director1")


@pytest.fixture()
def sample_project(db, priority_levels, phases, manager_user, employee_user):
    project = Project(
        project_number="PRJ-1001", title="Sample Project", priority_level_id=priority_levels["High"].id,
        original_priority_level_id=priority_levels["High"].id, phase_id=phases["Development"].id,
        owner_id=manager_user.id, target_deadline=date.today() + timedelta(days=10),
        original_deadline=date.today() + timedelta(days=10),
    )
    db.session.add(project)
    db.session.commit()
    db.session.add(ProjectAssignment(project_id=project.id, user_id=employee_user.id))
    db.session.commit()
    return project


@pytest.fixture()
def sample_idea(db, employee_user):
    idea = Idea(idea_number="IDA-1001", title="Sample Idea", submitted_by_id=employee_user.id, submission_date=date.today())
    db.session.add(idea)
    db.session.commit()
    return idea


@pytest.fixture()
def sample_chore(db, priority_levels, employee_user):
    chore = Chore(
        chore_number="CHR-1001", title="Sample Chore", assigned_user_id=employee_user.id,
        priority_level_id=priority_levels["Normal"].id, recurrence_type="weekly",
        recurrence_config={}, due_date=date.today(), next_scheduled_at=date.today(),
    )
    db.session.add(chore)
    db.session.commit()
    return chore

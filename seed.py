"""Seeds roles, permissions, catalogs, demo users, and a handful of demo
work items (with some priority/interruption/deadline history already
logged) so the app isn't empty on first run.

Run via `flask seed-db`. Safe to re-run: it skips creation if roles already
exist, so it won't duplicate data on a database that's already seeded.
"""

from datetime import date, datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    Chore, Client, Comment, Department, Idea, Interruption, PriorityEvent,
    PriorityLevel, Project, ProjectAssignment, ProjectPhase, Role, Tag,
    Team, TimeEntry, User, WorkflowRule, WorkRequest,
)
from app.models.deadline import DeadlineRevision
from app.services.activity import log_activity
from app.services.chore_service import generate_occurrence_if_due
from app.services.numbering import next_number

DEMO_PASSWORD = "priorityshift"

ROLE_PERMISSIONS = {
    "President": [
        "view_own_dashboard", "view_team_dashboard", "view_org_dashboard", "create_request",
        "create_project", "create_chore", "create_idea", "assign_work", "change_priority",
        "approve_priority_change", "change_deadline", "approve_deadline_change",
        "view_financial_classification", "view_client_info", "manage_users", "manage_roles",
        "manage_departments", "manage_teams", "configure_workflows", "manage_tags",
        "export_reports", "access_audit_logs", "review_requests", "complete_chore",
        "convert_idea", "comment",
    ],
    "Vice President": [
        "view_own_dashboard", "view_team_dashboard", "view_org_dashboard", "create_request",
        "create_project", "create_chore", "create_idea", "assign_work", "change_priority",
        "approve_priority_change", "change_deadline", "approve_deadline_change",
        "view_financial_classification", "view_client_info", "manage_users",
        "manage_departments", "manage_teams", "configure_workflows", "manage_tags",
        "export_reports", "access_audit_logs", "review_requests", "complete_chore",
        "convert_idea", "comment",
    ],
    "Director": [
        "view_own_dashboard", "view_team_dashboard", "view_org_dashboard", "create_request",
        "create_project", "create_chore", "create_idea", "assign_work", "change_priority",
        "approve_priority_change", "change_deadline", "approve_deadline_change",
        "view_financial_classification", "view_client_info", "export_reports",
        "access_audit_logs", "review_requests", "complete_chore", "convert_idea", "comment",
    ],
    "Manager": [
        "view_own_dashboard", "view_team_dashboard", "create_request", "create_project",
        "create_chore", "create_idea", "assign_work", "change_priority", "change_deadline",
        "view_client_info", "export_reports", "review_requests", "complete_chore",
        "convert_idea", "comment",
    ],
    "Team Lead": [
        "view_own_dashboard", "view_team_dashboard", "create_request", "create_project",
        "create_chore", "create_idea", "assign_work", "change_priority", "complete_chore",
        "convert_idea", "comment",
    ],
    "Employee": [
        "view_own_dashboard", "create_request", "create_idea", "complete_chore", "comment",
    ],
}

PRIORITY_LEVELS = [
    ("Critical", 1, "#e11d48", "alert-triangle", True),
    ("Urgent", 2, "#ea580c", "flame", False),
    ("High", 3, "#d97706", "arrow-up", False),
    ("Normal", 4, "#0284c7", "flag", False),
    ("Low", 5, "#64748b", "arrow-down", False),
    ("Paused", 6, "#7c3aed", "pause", False),
]

PROJECT_PHASES = [
    ("Requested", 1, False), ("Discovery", 2, False), ("Requirements Gathering", 3, False),
    ("Planning", 4, False), ("Awaiting Approval", 5, False), ("Development", 6, False),
    ("Testing", 7, False), ("Client Review", 8, False), ("Deployment", 9, False),
    ("Monitoring", 10, False), ("Completed", 11, True), ("On Hold", 12, False), ("Cancelled", 13, True),
]


def ensure_catalog():
    """Create roles, priority levels, and project phases if they don't
    already exist. Idempotent — safe to call any time (e.g. every time the
    control panel opens), unlike the full demo dataset below."""
    roles = {}
    for i, name in enumerate(["President", "Vice President", "Director", "Manager", "Team Lead", "Employee"], start=1):
        role = Role.query.filter_by(name=name).first()
        if not role:
            role = Role(name=name, hierarchy_level=i, permissions=ROLE_PERMISSIONS[name])
            db.session.add(role)
        roles[name] = role

    levels = {}
    for name, rank, color, icon, ack in PRIORITY_LEVELS:
        level = PriorityLevel.query.filter_by(name=name).first()
        if not level:
            level = PriorityLevel(name=name, rank=rank, color=color, icon=icon, requires_acknowledgment=ack)
            db.session.add(level)
        levels[name] = level

    phases = {}
    for name, rank, terminal in PROJECT_PHASES:
        phase = ProjectPhase.query.filter_by(name=name).first()
        if not phase:
            phase = ProjectPhase(name=name, rank=rank, is_terminal=terminal)
            db.session.add(phase)
        phases[name] = phase

    db.session.commit()
    return {"roles": roles, "levels": levels, "phases": phases}


def create_admin_user(full_name, username, email, password):
    """Creates the catalog if needed, then a user with the highest-authority
    role (President). This is what the desktop control panel's "Create Admin
    Account" action calls — it's the CLI-free path to a first account."""
    username = username.strip().lower()
    email = email.strip().lower()

    if not full_name or not username or not email or not password:
        raise ValueError("Full name, username, email, and password are all required.")
    if User.query.filter_by(username=username).first():
        raise ValueError(f"Username '{username}' is already taken.")
    if User.query.filter_by(email=email).first():
        raise ValueError(f"Email '{email}' is already in use.")

    catalog = ensure_catalog()
    president_role = catalog["roles"]["President"]

    user = User(username=username, email=email, full_name=full_name, role_id=president_role.id, active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def run_seed():
    if Role.query.first():
        print("Already seeded — skipping. Delete the database to reseed from scratch.")
        return

    catalog = ensure_catalog()
    roles, levels, phases = catalog["roles"], catalog["levels"], catalog["phases"]

    engineering = Department(name="Engineering", description="Product development")
    operations = Department(name="Operations", description="Internal operations")
    sales = Department(name="Sales", description="Sales and account management")
    support = Department(name="Support", description="Customer support")
    db.session.add_all([engineering, operations, sales, support])
    db.session.flush()

    platform_team = Team(name="Platform Team", department_id=engineering.id)
    client_team = Team(name="Client Services Team", department_id=engineering.id)
    db.session.add_all([platform_team, client_team])
    db.session.flush()

    acme = Client(name="Acme Corp")
    globex = Client(name="Globex Inc")
    db.session.add_all([acme, globex])

    db.session.add(WorkflowRule(
        rule_type="max_critical_per_developer", scope="global", threshold=2, active=True,
        description="No developer should be juggling more than 2 Critical projects at once.",
    ))
    db.session.add(WorkflowRule(
        rule_type="require_exec_approval_for_critical", scope="global", active=True,
        description="Raising a project to Critical needs a President/VP/Director's approval.",
    ))
    db.session.flush()

    def make_user(username, full_name, email, role_name, manager=None, team_lead=None, teams=None, departments=None, color="#6366f1"):
        u = User(
            username=username, email=email, full_name=full_name, role_id=roles[role_name].id,
            manager_id=manager.id if manager else None, team_lead_id=team_lead.id if team_lead else None,
            avatar_color=color,
        )
        u.set_password(DEMO_PASSWORD)
        db.session.add(u)
        db.session.flush()
        if teams:
            u.teams = teams
        if departments:
            u.departments = departments
        return u

    sarah = make_user("sarah.president", "Sarah Kim", "sarah.kim@example.com", "President", departments=[engineering], color="#dc2626")
    victor = make_user("victor.vp", "Victor Ruiz", "victor.ruiz@example.com", "Vice President", manager=sarah, departments=[engineering], color="#ea580c")
    dana = make_user("dana.director", "Dana Whitfield", "dana.whitfield@example.com", "Director", manager=victor, departments=[engineering], color="#d97706")
    mike = make_user("mike.manager", "Mike Torres", "mike.torres@example.com", "Manager", manager=dana, teams=[platform_team], departments=[engineering], color="#0284c7")
    tara = make_user("tara.lead", "Tara Nguyen", "tara.nguyen@example.com", "Team Lead", manager=mike, teams=[platform_team], departments=[engineering], color="#0891b2")
    eli = make_user("eli.dev", "Eli Brooks", "eli.brooks@example.com", "Employee", manager=mike, team_lead=tara, teams=[platform_team], departments=[engineering], color="#7c3aed")
    priya = make_user("priya.dev", "Priya Shah", "priya.shah@example.com", "Employee", manager=mike, team_lead=tara, teams=[client_team], departments=[engineering], color="#c026d3")
    omar = make_user("omar.dev", "Omar Farouk", "omar.farouk@example.com", "Employee", manager=mike, team_lead=tara, teams=[platform_team], departments=[engineering], color="#059669")
    jen_ops = make_user("jen.ops", "Jen Alvarez", "jen.alvarez@example.com", "Employee", departments=[operations], color="#65a30d")
    db.session.flush()

    today = date.today()

    def make_project(number_seed, title, description, priority_name, phase_name, owner, assignees,
                      requested_by, requesting_department, deadline_offset_days, effort, percent,
                      health="on_track", is_client=False, is_paid=False, client=None, category="standard"):
        p = Project(
            project_number="PENDING", title=title, description=description,
            is_client=is_client, is_paid=is_paid, category=category, client_id=client.id if client else None,
            priority_level_id=levels[priority_name].id, original_priority_level_id=levels[priority_name].id,
            phase_id=phases[phase_name].id, owner_id=owner.id if owner else None,
            requested_by_id=requested_by.id if requested_by else None,
            requesting_department_id=requesting_department.id if requesting_department else None,
            date_requested=today - timedelta(days=30), date_started=today - timedelta(days=25),
            target_deadline=today + timedelta(days=deadline_offset_days),
            original_deadline=today + timedelta(days=deadline_offset_days),
            estimated_effort_hours=effort, percent_complete=percent, health_status=health,
            last_activity_at=datetime.utcnow(),
        )
        db.session.add(p)
        db.session.flush()
        p.project_number = next_number(Project)
        for u in assignees:
            db.session.add(ProjectAssignment(project_id=p.id, user_id=u.id))
        log_activity("project", p.id, "created", f"Project created by {requested_by.full_name if requested_by else 'system'}")
        return p

    proj_billing = make_project(
        1, "Client Billing Portal Redesign", "Modernize the self-service billing portal for Acme Corp.",
        "Critical", "Development", mike, [eli], dana, engineering, 5, 120, 55,
        health="at_risk", is_client=True, is_paid=True, client=acme,
    )
    proj_migration = make_project(
        2, "Database Migration to Postgres", "Migrate the legacy MySQL cluster to PostgreSQL.",
        "High", "Testing", mike, [omar], mike, engineering, 20, 80, 70, category="infrastructure",
    )
    proj_mobile = make_project(
        3, "Globex Mobile App v2", "New mobile app release for Globex Inc.",
        "Urgent", "Client Review", mike, [priya], victor, engineering, 10, 200, 40,
        is_client=True, is_paid=True, client=globex,
    )
    proj_internal_tool = make_project(
        4, "Internal Time Tracking Tool", "Small internal tool for logging billable hours.",
        "Normal", "Planning", tara, [eli, priya], tara, engineering, 45, 40, 10,
    )
    proj_security = make_project(
        5, "Security Audit Remediation", "Address findings from Q2 external security audit.",
        "High", "Development", dana, [omar], dana, engineering, 14, 60, 30, category="compliance",
    )
    proj_paused = make_project(
        6, "Legacy Reports Rewrite", "Rewrite legacy reporting module.",
        "Paused", "On Hold", mike, [eli], mike, engineering, 90, 100, 5,
    )

    # --- A documented priority override with full audit trail ---
    event = PriorityEvent(
        item_type="project", item_id=proj_billing.id,
        occurred_at=datetime.utcnow() - timedelta(days=2),
        requested_by_id=dana.id, approved_by_id=victor.id,
        previous_priority_level_id=levels["High"].id, new_priority_level_id=levels["Critical"].id,
        reason="Acme escalated a payment-processing bug affecting live invoices.",
        business_justification="Acme represents 18% of recurring revenue; the bug blocks their AR close.",
        expected_interruption_minutes=480, displaced_item_type="project", displaced_item_id=proj_migration.id,
        displaced_summary=f"{proj_migration.project_number} (Eli Brooks's prior top priority)",
        is_temporary=False, developer_acknowledged_at=datetime.utcnow() - timedelta(days=2, hours=-1),
        developer_acknowledged_by_id=eli.id,
    )
    event.affected_developers = [eli]
    db.session.add(event)
    proj_billing.reprioritization_count += 1
    log_activity("project", proj_billing.id, "priority_changed", "Priority changed from High to Critical — Acme escalated a payment-processing bug.", actor=dana)

    # A deadline revision caused by that same interruption
    original_deadline = proj_billing.target_deadline
    db.session.add(DeadlineRevision(
        project_id=proj_billing.id, previous_deadline=original_deadline,
        new_deadline=original_deadline + timedelta(days=4), changed_at=datetime.utcnow() - timedelta(days=2),
        reason="Priority interruption (Critical): Acme escalated a payment-processing bug.",
        priority_event_id=event.id, changed_by_id=dana.id, estimated_hours_lost=8.0,
    ))
    proj_billing.revised_deadline = original_deadline + timedelta(days=4)
    proj_billing.deadline_revision_count += 1

    # Interruption log entries
    db.session.add(Interruption(
        user_id=eli.id, interrupted_by_id=dana.id, project_id=proj_migration.id,
        new_task_description="Fix Acme invoice payment bug", reason="Client-escalated production issue",
        start_time=datetime.utcnow() - timedelta(days=2), end_time=datetime.utcnow() - timedelta(days=2) + timedelta(hours=8),
        duration_minutes=480, context_switch_minutes=45, resumed_original=True, deadline_affected=True,
        priority_event_id=event.id,
    ))
    proj_migration.interruption_count += 1
    proj_migration.total_interruption_minutes += 525

    db.session.add(Interruption(
        user_id=omar.id, interrupted_by_id=jen_ops.id, project_id=proj_security.id,
        new_task_description="Rotate leaked API credential", reason="Operations found a leaked key in a log export",
        start_time=datetime.utcnow() - timedelta(days=6), end_time=datetime.utcnow() - timedelta(days=6) + timedelta(hours=2),
        duration_minutes=120, context_switch_minutes=20, resumed_original=True, deadline_affected=False,
    ))
    proj_security.interruption_count += 1
    proj_security.total_interruption_minutes += 140

    # Time entries feeding the workload report
    for u, proj, hours, category in [
        (eli, proj_billing, 8, "unplanned"), (eli, proj_migration, 30, "planned"),
        (omar, proj_migration, 40, "planned"), (omar, proj_security, 18, "planned"),
        (omar, proj_security, 2, "unplanned"), (priya, proj_mobile, 60, "planned"),
        (tara, proj_internal_tool, 6, "planned"),
    ]:
        db.session.add(TimeEntry(user_id=u.id, item_type="project", item_id=proj.id, entry_date=today - timedelta(days=3), hours=hours, category=category))

    # --- Chores ---
    def make_chore(title, description, assigned_user, priority_name, recurrence_type, config, due_offset, requested_by=None):
        c = Chore(
            chore_number="PENDING", title=title, description=description,
            assigned_user_id=assigned_user.id if assigned_user else None,
            requested_by_id=requested_by.id if requested_by else mike.id,
            priority_level_id=levels[priority_name].id, recurrence_type=recurrence_type,
            recurrence_config=config, due_date=today + timedelta(days=due_offset),
            next_scheduled_at=today + timedelta(days=due_offset),
        )
        db.session.add(c)
        db.session.flush()
        c.chore_number = next_number(Chore)
        generate_occurrence_if_due(c, today=c.next_scheduled_at)
        log_activity("chore", c.id, "created", "Chore created", actor=mike)
        return c

    make_chore("Defendify Security Training", "Monthly security awareness training module.", eli, "Normal", "specific_day_of_month", {"day_of_month": 15}, -2)
    make_chore("Server Patching", "Apply OS security patches to production servers.", omar, "High", "monthly", {}, 3)
    make_chore("Weekly Status Report", "Compile weekly status report for leadership.", tara, "Normal", "weekly", {}, 1)
    make_chore("Dependency Audit", "Audit third-party dependencies for known vulnerabilities.", priya, "Normal", "quarterly", {}, 25)
    make_chore("Q3 License Renewal", "Renew annual software licenses.", mike, "Urgent", "one_time", {}, 7)

    # --- Ideas ---
    idea1 = Idea(idea_number="PENDING", title="Slack notifications for priority changes", description="Post to a Slack channel whenever a project's priority changes.", submitted_by_id=eli.id, submission_date=today - timedelta(days=10), department_id=engineering.id, potential_value="Faster awareness of reprioritization across the team.", expected_benefit="Less time lost to people not knowing priorities shifted.", votes_count=4)
    db.session.add(idea1)
    db.session.flush()
    idea1.idea_number = next_number(Idea)

    idea2 = Idea(idea_number="PENDING", title="Client self-service status page", description="Let clients see project phase and health without asking.", submitted_by_id=priya.id, submission_date=today - timedelta(days=20), department_id=sales.id, potential_value="Fewer status-check emails from clients.", votes_count=2)
    db.session.add(idea2)
    db.session.flush()
    idea2.idea_number = next_number(Idea)

    # --- Work requests ---
    req1 = WorkRequest(
        request_number="PENDING", title="Add SSO login for Globex", description="Globex wants SAML SSO for their users.",
        business_need="Contract renewal is contingent on SSO support.", requested_by_id=victor.id,
        requesting_department_id=sales.id, desired_completion_date=today + timedelta(days=60),
        requested_priority_id=levels["High"].id, is_client=True, is_paid=True,
        estimated_business_impact="Retains a $200k/yr contract.", approver_id=dana.id,
    )
    db.session.add(req1)
    db.session.flush()
    req1.request_number = next_number(WorkRequest)

    db.session.add(Comment(item_type="project", item_id=proj_billing.id, author_id=dana.id, body="Confirmed with Acme this is our top priority until resolved.", is_decision=True))
    db.session.add(Comment(item_type="project", item_id=proj_migration.id, author_id=eli.id, body="Paused testing to handle the Acme fire — will resume Thursday.", is_blocker=False))

    db.session.commit()
    print(f"Seed complete. Demo users all use password: {DEMO_PASSWORD}")
    print("Try logging in as: sarah.president, victor.vp, dana.director, mike.manager, tara.lead, eli.dev, priya.dev, omar.dev, jen.ops")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        run_seed()

from functools import wraps

from flask import abort
from flask_login import current_user, login_required

# The full permission registry. Admins can toggle these per-role in
# Admin > Roles without any code change — this list is just the vocabulary.
PERMISSIONS = [
    ("view_own_dashboard", "View own dashboard", "See your personal workload dashboard."),
    ("view_team_dashboard", "View team dashboards", "See workload dashboards for a team."),
    ("view_org_dashboard", "View organization dashboard", "See the org-wide central dashboard."),
    ("create_request", "Create work requests", "Submit new work requests for review."),
    ("create_project", "Create projects", "Create new project records."),
    ("create_chore", "Create chores", "Create new recurring or one-time chores."),
    ("create_idea", "Create ideas", "Submit new ideas."),
    ("assign_work", "Assign work", "Assign projects/chores to developers."),
    ("change_priority", "Change priority", "Raise or lower a project/chore's priority."),
    ("approve_priority_change", "Approve priority changes", "Approve high-impact priority changes."),
    ("change_deadline", "Change deadlines", "Revise a project's deadline."),
    ("approve_deadline_change", "Approve deadline changes", "Approve a deadline revision."),
    ("view_financial_classification", "View paid/unpaid classification", "See paid vs. unpaid designation."),
    ("view_client_info", "View client information", "See client-identifying information."),
    ("manage_users", "Manage users", "Create, edit, and deactivate user accounts."),
    ("manage_roles", "Manage roles & permissions", "Rename roles and edit their permissions."),
    ("manage_departments", "Manage departments", "Create and edit departments."),
    ("manage_teams", "Manage teams", "Create and edit teams."),
    ("configure_workflows", "Configure workflow rules", "Edit priority levels, phases, and workflow rules."),
    ("manage_tags", "Manage tags", "Create and edit tags."),
    ("export_reports", "Export reports", "Export reports to CSV."),
    ("access_audit_logs", "Access audit logs", "View full activity/audit history."),
    ("review_requests", "Review work requests", "Accept, reject, or convert work requests."),
    ("complete_chore", "Complete chores", "Mark chore occurrences complete/skip/escalate."),
    ("convert_idea", "Convert ideas", "Convert an idea into a project or chore."),
    ("comment", "Comment", "Add comments to work items."),
]

PERMISSION_KEYS = {key for key, _, _ in PERMISSIONS}


def requires_permission(key: str):
    """Route decorator: require login AND that the current user's role
    grants `key`. 403s rather than silently hiding the action."""

    if key not in PERMISSION_KEYS:
        raise ValueError(f"Unknown permission key: {key}")

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            if not current_user.has_permission(key):
                abort(403)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator


def user_has_permission(user, key: str) -> bool:
    return bool(user and user.is_authenticated and user.has_permission(key))

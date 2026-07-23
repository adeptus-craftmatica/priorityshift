from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Team, User
from app.services.dashboard_service import get_personal_dashboard_context
from app.services.permissions import requires_permission
from app.services.priority_queue import get_org_dashboard_rows, get_org_totals

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def personal():
    user_id = request.args.get("user_id", type=int)
    if user_id and user_id != current_user.id:
        if not (current_user.has_permission("view_team_dashboard") or current_user.has_permission("view_org_dashboard")):
            abort(403)
        target_user = User.query.get_or_404(user_id)
    else:
        target_user = current_user

    ctx = get_personal_dashboard_context(target_user)
    db.session.commit()  # persists any due/overdue reminder notifications generated above
    return render_template("dashboard/personal.html", target_user=target_user, **ctx)


@bp.route("/organization")
@requires_permission("view_org_dashboard")
def organization():
    rows = get_org_dashboard_rows()
    totals = get_org_totals()
    return render_template("dashboard/organization.html", rows=rows, totals=totals)


@bp.route("/team/<int:team_id>")
@requires_permission("view_team_dashboard")
def team(team_id):
    team_obj = Team.query.get_or_404(team_id)
    active_members = [u for u in team_obj.users if u.active]
    rows = get_org_dashboard_rows(users=active_members)
    totals = get_org_totals()
    return render_template("dashboard/team.html", team=team_obj, rows=rows, totals=totals)

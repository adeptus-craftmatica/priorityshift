from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.extensions import db
from app.models import (
    Chore, Client, Department, Idea, PriorityLevel, Project, ProjectPhase,
    Role, Tag, Team, User, WorkflowRule,
)
from app.blueprints.admin.forms import (
    ClientForm, DepartmentForm, PriorityLevelForm, ProjectPhaseForm, ResetPasswordForm,
    RoleForm, TagForm, TeamForm, UserForm, WorkflowRuleForm,
)
from app.services.permissions import PERMISSIONS, requires_permission
from app.services.user_lifecycle import archive_user, get_user_history, set_active, unarchive_user

bp = Blueprint("admin", __name__)


@bp.route("/")
@requires_permission("manage_users")
def index():
    counts = {
        "users": User.query.count(),
        "roles": Role.query.count(),
        "departments": Department.query.count(),
        "teams": Team.query.count(),
        "priority_levels": PriorityLevel.query.count(),
        "phases": ProjectPhase.query.count(),
        "workflow_rules": WorkflowRule.query.count(),
        "tags": Tag.query.count(),
        "clients": Client.query.count(),
        "projects": Project.query.count(),
        "chores": Chore.query.count(),
        "ideas": Idea.query.count(),
    }
    return render_template("admin/index.html", counts=counts)


# ---------- Users ----------

@bp.route("/users", methods=["GET", "POST"])
@requires_permission("manage_users")
def users():
    form = UserForm()
    form.role_id.choices = [(r.id, r.name) for r in Role.query.order_by(Role.hierarchy_level).all()]
    all_users = User.query.order_by(User.full_name).all()
    show_archived = request.args.get("show_archived") == "1"
    visible_users = all_users if show_archived else [u for u in all_users if not u.is_archived]
    form.manager_id.choices = [(0, "— None —")] + [(u.id, u.full_name) for u in all_users]
    form.team_lead_id.choices = form.manager_id.choices
    form.department_ids.choices = [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]
    form.team_ids.choices = [(t.id, t.name) for t in Team.query.order_by(Team.name).all()]
    form.client_id.choices = [(0, "— None (internal staff) —")] + [
        (c.id, c.name) for c in Client.query.order_by(Client.name).all()
    ]

    if form.validate_on_submit():
        if form.id.data:
            user = User.query.get_or_404(int(form.id.data))
        else:
            user = User()
            db.session.add(user)
        user.username = form.username.data.strip().lower()
        user.email = form.email.data.strip().lower()
        user.full_name = form.full_name.data
        user.role_id = form.role_id.data
        user.manager_id = form.manager_id.data or None
        user.team_lead_id = form.team_lead_id.data or None
        user.capacity_hours_per_week = form.capacity_hours_per_week.data or 40
        if form.id.data and form.active.data != user.active:
            # Route through the audited path — this checkbox is just
            # another way to reach the same active/inactive state as the
            # dedicated Lock/Unlock button, and must not bypass the trail.
            set_active(user, form.active.data, actor=current_user)
        else:
            user.active = form.active.data
        user.client_id = form.client_id.data or None
        if form.password.data:
            user.set_password(form.password.data)
        elif not user.password_hash:
            user.set_password("changeme123")
        user.departments = Department.query.filter(Department.id.in_(form.department_ids.data)).all()
        user.teams = Team.query.filter(Team.id.in_(form.team_ids.data)).all()
        db.session.commit()
        flash("User saved.", "success")
        return redirect(url_for("admin.users"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        user = User.query.get_or_404(edit_id)
        form = UserForm(obj=user)
        form.role_id.choices = [(r.id, r.name) for r in Role.query.order_by(Role.hierarchy_level).all()]
        form.manager_id.choices = [(0, "— None —")] + [(u.id, u.full_name) for u in all_users]
        form.team_lead_id.choices = form.manager_id.choices
        form.department_ids.choices = [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]
        form.team_ids.choices = [(t.id, t.name) for t in Team.query.order_by(Team.name).all()]
        form.client_id.choices = [(0, "— None (internal staff) —")] + [
            (c.id, c.name) for c in Client.query.order_by(Client.name).all()
        ]
        form.id.data = user.id
        form.manager_id.data = user.manager_id or 0
        form.team_lead_id.data = user.team_lead_id or 0
        form.department_ids.data = [d.id for d in user.departments]
        form.team_ids.data = [t.id for t in user.teams]
        form.client_id.data = user.client_id or 0

    return render_template("admin/users.html", form=form, users=visible_users, show_archived=show_archived)


@bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@requires_permission("manage_users")
def reset_password(user_id):
    target_user = User.query.get_or_404(user_id)
    form = ResetPasswordForm()

    if form.validate_on_submit():
        target_user.set_password(form.password.data)
        db.session.commit()
        flash(f"Password reset for {target_user.full_name}.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/reset_password.html", form=form, target_user=target_user)


@bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@requires_permission("manage_users")
def toggle_active(user_id):
    target_user = User.query.get_or_404(user_id)
    if target_user.id == current_user.id:
        flash("You can't lock yourself out — ask another admin to do this.", "error")
        return redirect(url_for("admin.users"))

    set_active(target_user, not target_user.active, actor=current_user)
    db.session.commit()
    flash(
        f"{target_user.full_name} {'unlocked' if target_user.active else 'locked out'}.",
        "success",
    )
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/archive", methods=["POST"])
@requires_permission("manage_users")
def archive(user_id):
    target_user = User.query.get_or_404(user_id)
    if target_user.id == current_user.id:
        flash("You can't archive your own account — ask another admin to do this.", "error")
        return redirect(url_for("admin.users"))

    archive_user(target_user, actor=current_user)
    db.session.commit()
    flash(f"{target_user.full_name} archived.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/unarchive", methods=["POST"])
@requires_permission("manage_users")
def unarchive(user_id):
    target_user = User.query.get_or_404(user_id)
    unarchive_user(target_user, actor=current_user)
    db.session.commit()
    flash(f"{target_user.full_name} restored from archive.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>/history")
@requires_permission("manage_users")
def user_history(user_id):
    target_user = User.query.get_or_404(user_id)
    entries = get_user_history(target_user)
    return render_template("admin/user_history.html", target_user=target_user, entries=entries)


# ---------- Roles ----------

@bp.route("/roles", methods=["GET", "POST"])
@requires_permission("manage_roles")
def roles():
    form = RoleForm()
    form.permissions.choices = [(key, label) for key, label, _ in PERMISSIONS]

    if form.validate_on_submit():
        if form.id.data:
            role = Role.query.get_or_404(int(form.id.data))
        else:
            role = Role()
            db.session.add(role)
        role.name = form.name.data
        role.hierarchy_level = form.hierarchy_level.data
        role.description = form.description.data
        role.permissions = form.permissions.data
        db.session.commit()
        flash("Role saved.", "success")
        return redirect(url_for("admin.roles"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        role = Role.query.get_or_404(edit_id)
        form = RoleForm(obj=role)
        form.permissions.choices = [(key, label) for key, label, _ in PERMISSIONS]
        form.id.data = role.id
        form.permissions.data = role.permissions or []

    return render_template(
        "admin/roles.html", form=form, roles=Role.query.order_by(Role.hierarchy_level).all(),
        all_permissions=PERMISSIONS,
    )


# ---------- Departments ----------

@bp.route("/departments", methods=["GET", "POST"])
@requires_permission("manage_departments")
def departments():
    form = DepartmentForm()
    if form.validate_on_submit():
        if form.id.data:
            dept = Department.query.get_or_404(int(form.id.data))
        else:
            dept = Department()
            db.session.add(dept)
        dept.name = form.name.data
        dept.description = form.description.data
        db.session.commit()
        flash("Department saved.", "success")
        return redirect(url_for("admin.departments"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        form = DepartmentForm(obj=Department.query.get_or_404(edit_id))
        form.id.data = edit_id

    return render_template("admin/departments.html", form=form, departments=Department.query.order_by(Department.name).all())


# ---------- Teams ----------

@bp.route("/teams", methods=["GET", "POST"])
@requires_permission("manage_teams")
def teams():
    form = TeamForm()
    form.department_id.choices = [(0, "— None —")] + [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]

    if form.validate_on_submit():
        if form.id.data:
            team = Team.query.get_or_404(int(form.id.data))
        else:
            team = Team()
            db.session.add(team)
        team.name = form.name.data
        team.description = form.description.data
        team.department_id = form.department_id.data or None
        db.session.commit()
        flash("Team saved.", "success")
        return redirect(url_for("admin.teams"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        team = Team.query.get_or_404(edit_id)
        form = TeamForm(obj=team)
        form.department_id.choices = [(0, "— None —")] + [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]
        form.id.data = team.id
        form.department_id.data = team.department_id or 0

    return render_template("admin/teams.html", form=form, teams=Team.query.order_by(Team.name).all())


# ---------- Priority levels ----------

@bp.route("/priority-levels", methods=["GET", "POST"])
@requires_permission("configure_workflows")
def priority_levels():
    form = PriorityLevelForm()
    if form.validate_on_submit():
        if form.id.data:
            level = PriorityLevel.query.get_or_404(int(form.id.data))
        else:
            level = PriorityLevel()
            db.session.add(level)
        level.name = form.name.data
        level.rank = form.rank.data
        level.color = form.color.data
        level.icon = form.icon.data
        level.requires_acknowledgment = form.requires_acknowledgment.data
        level.active = form.active.data
        db.session.commit()
        flash("Priority level saved.", "success")
        return redirect(url_for("admin.priority_levels"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        form = PriorityLevelForm(obj=PriorityLevel.query.get_or_404(edit_id))
        form.id.data = edit_id

    return render_template(
        "admin/priority_levels.html", form=form,
        levels=PriorityLevel.query.order_by(PriorityLevel.rank).all(),
    )


# ---------- Project phases ----------

@bp.route("/phases", methods=["GET", "POST"])
@requires_permission("configure_workflows")
def phases():
    form = ProjectPhaseForm()
    if form.validate_on_submit():
        if form.id.data:
            phase = ProjectPhase.query.get_or_404(int(form.id.data))
        else:
            phase = ProjectPhase()
            db.session.add(phase)
        phase.name = form.name.data
        phase.rank = form.rank.data
        phase.is_terminal = form.is_terminal.data
        phase.active = form.active.data
        db.session.commit()
        flash("Phase saved.", "success")
        return redirect(url_for("admin.phases"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        form = ProjectPhaseForm(obj=ProjectPhase.query.get_or_404(edit_id))
        form.id.data = edit_id

    return render_template("admin/phases.html", form=form, phases=ProjectPhase.query.order_by(ProjectPhase.rank).all())


# ---------- Workflow rules ----------

@bp.route("/workflow-rules", methods=["GET", "POST"])
@requires_permission("configure_workflows")
def workflow_rules():
    form = WorkflowRuleForm()
    if form.validate_on_submit():
        if form.id.data:
            rule = WorkflowRule.query.get_or_404(int(form.id.data))
        else:
            rule = WorkflowRule()
            db.session.add(rule)
        rule.rule_type = form.rule_type.data
        rule.description = form.description.data
        rule.scope = form.scope.data
        rule.threshold = form.threshold.data
        rule.active = form.active.data
        db.session.commit()
        flash("Workflow rule saved.", "success")
        return redirect(url_for("admin.workflow_rules"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        form = WorkflowRuleForm(obj=WorkflowRule.query.get_or_404(edit_id))
        form.id.data = edit_id

    return render_template("admin/workflow_rules.html", form=form, rules=WorkflowRule.query.all())


# ---------- Tags ----------

@bp.route("/tags", methods=["GET", "POST"])
@requires_permission("manage_tags")
def tags():
    form = TagForm()
    if form.validate_on_submit():
        if form.id.data:
            tag = Tag.query.get_or_404(int(form.id.data))
        else:
            tag = Tag()
            db.session.add(tag)
        tag.name = form.name.data
        tag.color = form.color.data
        db.session.commit()
        flash("Tag saved.", "success")
        return redirect(url_for("admin.tags"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        form = TagForm(obj=Tag.query.get_or_404(edit_id))
        form.id.data = edit_id

    return render_template("admin/tags.html", form=form, tags=Tag.query.order_by(Tag.name).all())


# ---------- Clients ----------

@bp.route("/clients", methods=["GET", "POST"])
@requires_permission("manage_departments")
def clients():
    form = ClientForm()
    form.account_owner_id.choices = [(0, "— None —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(active=True).order_by(User.full_name).all()
    ]
    if form.validate_on_submit():
        if form.id.data:
            client = Client.query.get_or_404(int(form.id.data))
        else:
            client = Client()
            db.session.add(client)
        client.name = form.name.data
        client.account_owner_id = form.account_owner_id.data or None
        client.active = form.active.data
        db.session.commit()
        flash("Client saved.", "success")
        return redirect(url_for("admin.clients"))

    edit_id = request.args.get("edit_id", type=int)
    if edit_id:
        client = Client.query.get_or_404(edit_id)
        form = ClientForm(obj=client)
        form.account_owner_id.choices = [(0, "— None —")] + [
            (u.id, u.full_name) for u in User.query.filter_by(active=True).order_by(User.full_name).all()
        ]
        form.id.data = client.id
        form.account_owner_id.data = client.account_owner_id or 0

    return render_template("admin/clients.html", form=form, clients=Client.query.order_by(Client.name).all())

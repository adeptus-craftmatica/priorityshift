from datetime import date, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import (
    Client, Comment, Department, Interruption, PriorityLevel,
    Project, ProjectAssignment, ProjectPhase, Tag, TimeEntry, User,
)
from app.blueprints.projects.forms import HealthUpdateForm, InterruptionLogForm, ProjectForm, TimeEntryForm
from app.services.activity import get_timeline, log_activity
from app.services.attachments import list_attachments
from app.services.deadline_service import project_deadline_summary, revise_deadline
from app.services.notifications import notify
from app.services.numbering import next_number
from app.services.permissions import requires_permission
from app.services.priority_queue import get_committed_hours_for_user
from app.models.priority_event import PriorityEvent

bp = Blueprint("projects", __name__)


def _populate_choices(form):
    form.priority_level_id.choices = [
        (p.id, p.name) for p in PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank).all()
    ]
    form.phase_id.choices = [
        (p.id, p.name) for p in ProjectPhase.query.filter_by(active=True).order_by(ProjectPhase.rank).all()
    ]
    form.client_id.choices = [(0, "— None —")] + [(c.id, c.name) for c in Client.query.order_by(Client.name).all()]
    form.requesting_department_id.choices = [(0, "— None —")] + [
        (d.id, d.name) for d in Department.query.order_by(Department.name).all()
    ]
    users = User.query.filter_by(active=True).order_by(User.full_name).all()
    form.owner_id.choices = [(0, "— None —")] + [(u.id, u.full_name) for u in users]
    form.approving_manager_id.choices = [(0, "— None —")] + [(u.id, u.full_name) for u in users]
    form.assignee_ids.choices = [(u.id, u.full_name) for u in users]


def _build_timeline_rows(projects, window_start, window_end):
    """Positions each project as a left%/width% bar within a fixed date
    window — a plain CSS Gantt-lite, no charting library needed."""
    total_days = (window_end - window_start).days
    rows = []
    for p in projects:
        start = p.date_started or p.date_requested
        end = p.revised_deadline or p.target_deadline
        if not start or not end or end < window_start or start > window_end:
            continue
        clamped_start = max(start, window_start)
        clamped_end = min(end, window_end)
        left_pct = (clamped_start - window_start).days / total_days * 100
        width_pct = max(1.5, (clamped_end - clamped_start).days / total_days * 100)
        rows.append({"project": p, "left_pct": round(left_pct, 2), "width_pct": round(width_pct, 2)})
    return rows


@bp.route("/")
@login_required
def list_view():
    view = request.args.get("view", "table")
    query = Project.query.filter_by(is_archived=False)

    priority_id = request.args.get("priority_id", type=int)
    phase_id = request.args.get("phase_id", type=int)
    assignee_id = request.args.get("assignee_id", type=int)
    department_id = request.args.get("department_id", type=int)
    client_id = request.args.get("client_id", type=int)
    health_status = request.args.get("health_status")
    blocked = request.args.get("blocked")
    q = request.args.get("q")

    if priority_id:
        query = query.filter_by(priority_level_id=priority_id)
    if phase_id:
        query = query.filter_by(phase_id=phase_id)
    if assignee_id:
        query = query.join(ProjectAssignment).filter(ProjectAssignment.user_id == assignee_id)
    if department_id:
        query = query.filter_by(requesting_department_id=department_id)
    if client_id:
        query = query.filter_by(client_id=client_id)
    if health_status:
        query = query.filter_by(health_status=health_status)
    if blocked == "1":
        query = query.filter(Project.roadblocks.isnot(None), Project.roadblocks != "")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Project.title.ilike(like), Project.project_number.ilike(like), Project.description.ilike(like)))

    projects = query.all()

    if view == "queue":
        projects.sort(key=lambda p: (p.priority_level.rank if p.priority_level else 999, p.target_deadline or date.max))
    else:
        projects.sort(key=lambda p: p.updated_at, reverse=True)

    phases = ProjectPhase.query.filter_by(active=True).order_by(ProjectPhase.rank).all()
    projects_by_phase = {phase.id: [p for p in projects if p.phase_id == phase.id] for phase in phases}

    timeline_window_start = date.today() - timedelta(weeks=4)
    timeline_window_end = date.today() + timedelta(weeks=12)
    timeline_rows = _build_timeline_rows(projects, timeline_window_start, timeline_window_end)

    return render_template(
        "projects/list.html",
        projects=projects, view=view, projects_by_phase=projects_by_phase,
        priority_levels=PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank).all(),
        phases=phases,
        departments=Department.query.order_by(Department.name).all(),
        clients=Client.query.order_by(Client.name).all(),
        timeline_rows=timeline_rows,
        timeline_window_start=timeline_window_start,
        timeline_window_end=timeline_window_end,
    )


@bp.route("/<int:project_id>/phase-ajax", methods=["POST"])
@login_required
def update_phase_ajax(project_id):
    project = Project.query.get_or_404(project_id)
    phase = ProjectPhase.query.get_or_404(request.form.get("phase_id", type=int))
    old_phase = project.phase.name if project.phase else "none"
    project.phase_id = phase.id
    project.last_activity_at = db.func.now()
    log_activity("project", project.id, "phase_changed", f"Phase changed from {old_phase} to {phase.name}", actor=current_user)
    db.session.commit()
    return jsonify({"success": True, "phase_id": phase.id, "phase_name": phase.name})


@bp.route("/new", methods=["GET", "POST"])
@requires_permission("create_project")
def create():
    form = ProjectForm()
    _populate_choices(form)

    if form.validate_on_submit():
        default_priority = PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank.desc()).first()
        phase = ProjectPhase.query.get(form.phase_id.data)

        project = Project(
            project_number="PENDING",
            title=form.title.data,
            description=form.description.data,
            category=form.category.data,
            is_client=form.is_client.data,
            is_paid=form.is_paid.data,
            client_id=form.client_id.data or None,
            priority_level_id=form.priority_level_id.data,
            original_priority_level_id=form.priority_level_id.data,
            phase_id=form.phase_id.data,
            requested_by_id=current_user.id,
            requesting_department_id=form.requesting_department_id.data or None,
            owner_id=form.owner_id.data or None,
            approving_manager_id=form.approving_manager_id.data or None,
            date_requested=form.date_requested.data or date.today(),
            date_started=form.date_started.data,
            target_deadline=form.target_deadline.data,
            original_deadline=form.target_deadline.data,
            estimated_effort_hours=form.estimated_effort_hours.data,
            percent_complete=form.percent_complete.data or 0,
            risks=form.risks.data,
            roadblocks=form.roadblocks.data,
            notes=form.notes.data,
            related_links=form.related_links.data,
            last_activity_at=db.func.now(),
        )
        db.session.add(project)
        db.session.flush()
        project.project_number = next_number(Project)

        for user_id in form.assignee_ids.data:
            db.session.add(ProjectAssignment(project_id=project.id, user_id=user_id))
        db.session.flush()
        _notify_new_assignees(project, form.assignee_ids.data)

        _apply_tags(project, form.tag_names.data)

        log_activity("project", project.id, "created", f"Project created by {current_user.full_name}", actor=current_user)
        db.session.commit()
        flash(f"Project {project.project_number} created.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("projects/form.html", form=form, project=None)


def _notify_new_assignees(project, user_ids):
    """Notifies newly-assigned developers, and warns whoever's assigning
    them if it pushes that developer over their weekly capacity — a
    lightweight version of the spec's "capacity conflict" check, done at
    the moment of assignment rather than waiting for a report to surface it."""
    for user_id in user_ids:
        user = User.query.get(user_id)
        if not user:
            continue
        notify(
            user, "assignment", f"You were assigned to {project.title}",
            body=f"{project.project_number} · requested by {current_user.full_name}",
            item_type="project", item_id=project.id,
        )
        committed = get_committed_hours_for_user(user)
        capacity = user.capacity_hours_per_week or 40
        if committed > capacity:
            notify(
                current_user, "capacity_conflict",
                f"{user.full_name} is over capacity",
                body=f"{committed:.1f}h committed vs {capacity:.1f}h/week capacity after this assignment.",
                item_type="project", item_id=project.id,
            )


def _apply_tags(project, tag_names_csv):
    if not tag_names_csv:
        return
    names = [n.strip() for n in tag_names_csv.split(",") if n.strip()]
    project.tags = []
    for name in names:
        tag = Tag.query.filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            db.session.add(tag)
        project.tags.append(tag)


@bp.route("/<int:project_id>")
@login_required
def detail(project_id):
    project = Project.query.get_or_404(project_id)
    timeline = get_timeline("project", project.id)
    comments = (
        Comment.query.filter_by(item_type="project", item_id=project.id, parent_comment_id=None)
        .order_by(Comment.is_pinned.desc(), Comment.created_at.desc())
        .all()
    )
    priority_events = (
        PriorityEvent.query.filter_by(item_type="project", item_id=project.id)
        .order_by(PriorityEvent.occurred_at.desc())
        .all()
    )
    interruptions = (
        Interruption.query.filter_by(project_id=project.id).order_by(Interruption.start_time.desc()).all()
    )
    deadline_summary = project_deadline_summary(project)
    attachments = list_attachments("project", project.id)

    return render_template(
        "projects/detail.html",
        project=project, timeline=timeline, comments=comments,
        priority_events=priority_events, interruptions=interruptions,
        deadline_summary=deadline_summary, attachments=attachments,
        phases=ProjectPhase.query.filter_by(active=True).order_by(ProjectPhase.rank).all(),
        interruption_form=InterruptionLogForm(), time_form=TimeEntryForm(),
        health_form=HealthUpdateForm(health_status=project.health_status, health_reason=project.health_reason),
    )


@bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def edit(project_id):
    project = Project.query.get_or_404(project_id)
    if not (current_user.has_permission("create_project") or current_user.id == project.owner_id):
        abort(403)

    form = ProjectForm(obj=project)
    _populate_choices(form)
    if request.method == "GET":
        form.client_id.data = project.client_id or 0
        form.requesting_department_id.data = project.requesting_department_id or 0
        form.owner_id.data = project.owner_id or 0
        form.approving_manager_id.data = project.approving_manager_id or 0
        form.assignee_ids.data = [a.user_id for a in project.assignments]
        form.tag_names.data = ", ".join(t.name for t in project.tags)

    if form.validate_on_submit():
        project.title = form.title.data
        project.description = form.description.data
        project.category = form.category.data
        project.is_client = form.is_client.data
        project.is_paid = form.is_paid.data
        project.client_id = form.client_id.data or None
        project.phase_id = form.phase_id.data
        project.requesting_department_id = form.requesting_department_id.data or None
        project.owner_id = form.owner_id.data or None
        project.approving_manager_id = form.approving_manager_id.data or None
        project.date_requested = form.date_requested.data
        project.date_started = form.date_started.data

        new_deadline = form.target_deadline.data
        deadline_pending = False
        if new_deadline and new_deadline != project.target_deadline:
            # Route through the deadline service rather than assigning
            # directly — otherwise this edit form silently overwrites the
            # deadline with no DeadlineRevision row, breaking the "every
            # deadline change is preserved" audit trail for anything that
            # didn't go through a priority change.
            revision = revise_deadline(
                project, new_deadline,
                reason="Deadline updated via project edit form.",
                changed_by=current_user,
            )
            deadline_pending = revision.status == "pending"
        elif not new_deadline:
            project.target_deadline = None

        project.estimated_effort_hours = form.estimated_effort_hours.data
        project.percent_complete = form.percent_complete.data or 0
        project.risks = form.risks.data
        project.roadblocks = form.roadblocks.data
        project.notes = form.notes.data
        project.related_links = form.related_links.data
        project.last_activity_at = db.func.now()

        existing_ids = {a.user_id for a in project.assignments}
        new_ids = set(form.assignee_ids.data)
        newly_assigned_ids = new_ids - existing_ids
        for uid in newly_assigned_ids:
            db.session.add(ProjectAssignment(project_id=project.id, user_id=uid))
        for assignment in list(project.assignments):
            if assignment.user_id not in new_ids:
                db.session.delete(assignment)
        db.session.flush()

        _notify_new_assignees(project, newly_assigned_ids)
        _apply_tags(project, form.tag_names.data)

        log_activity("project", project.id, "status_changed", "Project details updated", actor=current_user)
        db.session.commit()
        if deadline_pending:
            flash("Project updated. The deadline change needs approval before it takes effect.", "success")
        else:
            flash("Project updated.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    return render_template("projects/form.html", form=form, project=project)


@bp.route("/<int:project_id>/health", methods=["POST"])
@login_required
def update_health(project_id):
    project = Project.query.get_or_404(project_id)
    form = HealthUpdateForm()
    if form.validate_on_submit():
        project.health_status = form.health_status.data
        project.health_reason = form.health_reason.data
        project.health_is_manual_override = True
        log_activity(
            "project", project.id, "health_changed",
            f"Health set to {dict(form.health_status.choices)[form.health_status.data]} — {form.health_reason.data or 'no reason given'}",
            actor=current_user,
        )
        db.session.commit()
        flash("Health status updated.", "success")
    return redirect(url_for("projects.detail", project_id=project.id))


@bp.route("/<int:project_id>/phase", methods=["POST"])
@login_required
def update_phase(project_id):
    project = Project.query.get_or_404(project_id)
    phase = ProjectPhase.query.get_or_404(request.form.get("phase_id", type=int))
    old_phase = project.phase.name if project.phase else "none"
    project.phase_id = phase.id
    project.last_activity_at = db.func.now()
    log_activity("project", project.id, "phase_changed", f"Phase changed from {old_phase} to {phase.name}", actor=current_user)
    db.session.commit()
    flash("Phase updated.", "success")
    return redirect(url_for("projects.detail", project_id=project.id))


@bp.route("/<int:project_id>/archive", methods=["POST"])
@login_required
def toggle_archive(project_id):
    project = Project.query.get_or_404(project_id)
    project.is_archived = not project.is_archived
    log_activity(
        "project", project.id, "status_changed",
        "Project archived" if project.is_archived else "Project reactivated", actor=current_user,
    )
    db.session.commit()
    flash("Project archived." if project.is_archived else "Project reactivated.", "success")
    return redirect(url_for("projects.list_view"))


@bp.route("/<int:project_id>/interruptions", methods=["POST"])
@login_required
def log_interruption(project_id):
    project = Project.query.get_or_404(project_id)
    form = InterruptionLogForm()
    if form.validate_on_submit():
        from app.models.mixins import utcnow
        start = utcnow()
        interruption = Interruption(
            user_id=current_user.id,
            project_id=project.id,
            new_task_description=form.new_task_description.data,
            reason=form.reason.data,
            start_time=start,
            end_time=start,
            duration_minutes=form.duration_minutes.data,
            context_switch_minutes=form.context_switch_minutes.data or 0,
            resumed_original=form.resumed_original.data,
            deadline_affected=form.deadline_affected.data,
            notes=form.notes.data,
        )
        db.session.add(interruption)

        project.interruption_count = (project.interruption_count or 0) + 1
        project.total_interruption_minutes = (project.total_interruption_minutes or 0) + form.duration_minutes.data + (form.context_switch_minutes.data or 0)
        project.last_activity_at = db.func.now()

        log_activity(
            "project", project.id, "note_added",
            f"Interruption logged by {current_user.full_name}: {form.new_task_description.data} ({form.duration_minutes.data} min)",
            actor=current_user,
        )
        db.session.commit()
        flash("Interruption logged.", "success")
    else:
        flash("Couldn't log interruption — check the form.", "error")
    return redirect(url_for("projects.detail", project_id=project.id))


@bp.route("/<int:project_id>/time", methods=["POST"])
@login_required
def log_time(project_id):
    project = Project.query.get_or_404(project_id)
    form = TimeEntryForm()
    if form.validate_on_submit():
        entry = TimeEntry(
            user_id=current_user.id, item_type="project", item_id=project.id,
            entry_date=form.entry_date.data, hours=form.hours.data,
            category=form.category.data, notes=form.notes.data,
        )
        db.session.add(entry)
        project.actual_time_spent_hours = (project.actual_time_spent_hours or 0) + form.hours.data
        project.last_activity_at = db.func.now()
        log_activity("project", project.id, "time_entry", f"{form.hours.data}h logged ({form.category.data}) by {current_user.full_name}", actor=current_user)
        db.session.commit()
        flash("Time logged.", "success")
    return redirect(url_for("projects.detail", project_id=project.id))

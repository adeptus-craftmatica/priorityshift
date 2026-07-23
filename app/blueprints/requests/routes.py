from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Chore, Department, PriorityLevel, Project, ProjectPhase, User, WorkRequest
from app.blueprints.requests.forms import RequestDecisionForm, WorkRequestForm
from app.services.activity import log_activity
from app.services.numbering import next_number
from app.services.permissions import requires_permission

bp = Blueprint("requests", __name__)


def _populate_choices(form):
    form.requesting_department_id.choices = [(0, "— None —")] + [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]
    form.requested_priority_id.choices = [(0, "— Unspecified —")] + [
        (p.id, p.name) for p in PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank).all()
    ]
    form.approver_id.choices = [(0, "— Unassigned —")] + [
        (u.id, u.full_name) for u in User.query.filter_by(active=True).order_by(User.full_name).all()
    ]


@bp.route("/")
@login_required
def list_view():
    status = request.args.get("status", "new")
    query = WorkRequest.query
    if status != "all":
        query = query.filter_by(status=status)
    requests_ = query.order_by(WorkRequest.created_at.desc()).all()
    return render_template("requests/list.html", requests=requests_, status=status)


@bp.route("/new", methods=["GET", "POST"])
@requires_permission("create_request")
def create():
    form = WorkRequestForm()
    _populate_choices(form)

    if form.validate_on_submit():
        req = WorkRequest(
            request_number="PENDING",
            title=form.title.data,
            description=form.description.data,
            business_need=form.business_need.data,
            requested_by_id=current_user.id,
            requesting_department_id=form.requesting_department_id.data or None,
            desired_completion_date=form.desired_completion_date.data,
            requested_priority_id=form.requested_priority_id.data or None,
            is_client=form.is_client.data,
            is_paid=form.is_paid.data,
            estimated_business_impact=form.estimated_business_impact.data,
            approver_id=form.approver_id.data or None,
        )
        db.session.add(req)
        db.session.flush()
        req.request_number = next_number(WorkRequest)
        db.session.commit()
        flash(f"Request {req.request_number} submitted for review.", "success")
        return redirect(url_for("requests.detail", request_id=req.id))

    return render_template("requests/form.html", form=form)


@bp.route("/<int:request_id>")
@login_required
def detail(request_id):
    req = WorkRequest.query.get_or_404(request_id)
    return render_template("requests/detail.html", req=req, decision_form=RequestDecisionForm())


@bp.route("/<int:request_id>/decide", methods=["POST"])
@requires_permission("review_requests")
def decide(request_id):
    req = WorkRequest.query.get_or_404(request_id)
    form = RequestDecisionForm()
    valid_actions = {"accepted", "rejected", "needs_clarification", "scheduled", "escalated"}
    action = request.form.get("action")
    if action not in valid_actions:
        flash("Unknown action.", "error")
        return redirect(url_for("requests.detail", request_id=req.id))

    if form.validate_on_submit():
        req.status = action
        req.decision_notes = form.decision_notes.data
        req.decided_at = db.func.now()
        db.session.commit()
        flash(f"Request marked {action.replace('_', ' ')}.", "success")
    return redirect(url_for("requests.detail", request_id=req.id))


@bp.route("/<int:request_id>/convert-to-project", methods=["POST"])
@requires_permission("review_requests")
def convert_to_project(request_id):
    req = WorkRequest.query.get_or_404(request_id)
    default_phase = ProjectPhase.query.filter_by(active=True).order_by(ProjectPhase.rank).first()
    default_priority = req.requested_priority or PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank.desc()).first()

    project = Project(
        project_number="PENDING",
        title=req.title,
        description=req.description,
        is_client=req.is_client,
        is_paid=req.is_paid,
        priority_level_id=default_priority.id,
        original_priority_level_id=default_priority.id,
        phase_id=default_phase.id,
        requested_by_id=req.requested_by_id,
        requesting_department_id=req.requesting_department_id,
        approving_manager_id=req.approver_id,
        date_requested=date.today(),
        target_deadline=req.desired_completion_date,
        original_deadline=req.desired_completion_date,
        last_activity_at=db.func.now(),
    )
    db.session.add(project)
    db.session.flush()
    project.project_number = next_number(Project)

    req.status = "converted"
    req.converted_to_type = "project"
    req.converted_to_id = project.id
    req.related_project_id = project.id
    req.decided_at = db.func.now()

    log_activity("project", project.id, "created", f"Created from request {req.request_number}", actor=current_user)
    db.session.commit()
    flash(f"Converted to project {project.project_number}.", "success")
    return redirect(url_for("projects.detail", project_id=project.id))


@bp.route("/<int:request_id>/convert-to-chore", methods=["POST"])
@requires_permission("review_requests")
def convert_to_chore(request_id):
    req = WorkRequest.query.get_or_404(request_id)
    default_priority = req.requested_priority or PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank.desc()).first()

    chore = Chore(
        chore_number="PENDING",
        title=req.title,
        description=req.description,
        requested_by_id=req.requested_by_id,
        priority_level_id=default_priority.id,
        recurrence_type="one_time",
        recurrence_config={},
        due_date=req.desired_completion_date,
        next_scheduled_at=req.desired_completion_date or date.today(),
    )
    db.session.add(chore)
    db.session.flush()
    chore.chore_number = next_number(Chore)

    req.status = "converted"
    req.converted_to_type = "chore"
    req.converted_to_id = chore.id
    req.decided_at = db.func.now()

    log_activity("chore", chore.id, "created", f"Created from request {req.request_number}", actor=current_user)
    db.session.commit()
    flash(f"Converted to chore {chore.chore_number}.", "success")
    return redirect(url_for("chores.detail", chore_id=chore.id))

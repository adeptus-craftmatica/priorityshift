from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import DeadlineRevision
from app.services.deadline_service import approve_deadline_revision, reject_deadline_revision
from app.services.permissions import requires_permission

bp = Blueprint("deadline_approvals", __name__)


@bp.route("/")
@requires_permission("approve_priority_change")
def list_view():
    status = request.args.get("status", "pending")
    query = DeadlineRevision.query
    if status != "all":
        query = query.filter_by(status=status)
    revisions = query.order_by(DeadlineRevision.changed_at.desc()).all()
    return render_template("deadline_approvals/list.html", revisions=revisions, status=status)


@bp.route("/<int:revision_id>/approve", methods=["POST"])
@requires_permission("approve_priority_change")
def approve(revision_id):
    revision = DeadlineRevision.query.get_or_404(revision_id)
    if revision.status != "pending":
        flash("That request has already been decided.", "error")
        return redirect(url_for("deadline_approvals.list_view"))

    approve_deadline_revision(revision, current_user, notes=request.form.get("decision_notes"))
    db.session.commit()
    flash(f"Deadline change for {revision.project.project_number} approved.", "success")
    return redirect(url_for("deadline_approvals.list_view"))


@bp.route("/<int:revision_id>/reject", methods=["POST"])
@requires_permission("approve_priority_change")
def reject(revision_id):
    revision = DeadlineRevision.query.get_or_404(revision_id)
    if revision.status != "pending":
        flash("That request has already been decided.", "error")
        return redirect(url_for("deadline_approvals.list_view"))

    reject_deadline_revision(revision, current_user, notes=request.form.get("decision_notes"))
    db.session.commit()
    flash(f"Deadline change for {revision.project.project_number} rejected.", "success")
    return redirect(url_for("deadline_approvals.list_view"))

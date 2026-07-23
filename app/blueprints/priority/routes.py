from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Chore, PriorityEvent, PriorityLevel, Project
from app.blueprints.priority.forms import PriorityChangeForm
from app.services.permissions import requires_permission
from app.services.priority_service import commit_priority_change, preview_priority_change

bp = Blueprint("priority", __name__)


def _get_item(item_type, item_id):
    if item_type == "project":
        return Project.query.get_or_404(item_id)
    if item_type == "chore":
        return Chore.query.get_or_404(item_id)
    abort(404)


def _detail_url(item):
    if item.item_type == "project":
        return url_for("projects.detail", project_id=item.id)
    return url_for("chores.detail", chore_id=item.id)


@bp.route("/modal/<item_type>/<int:item_id>")
@requires_permission("change_priority")
def modal(item_type, item_id):
    item = _get_item(item_type, item_id)
    form = PriorityChangeForm()
    form.new_priority_level_id.choices = [
        (p.id, p.name) for p in PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank).all()
    ]
    return render_template("partials/priority_modal.html", item=item, item_type=item_type, form=form, preview=None)


@bp.route("/impact/<item_type>/<int:item_id>")
@requires_permission("change_priority")
def impact(item_type, item_id):
    item = _get_item(item_type, item_id)
    new_priority_level_id = request.args.get("new_priority_level_id", type=int)
    preview = None
    new_priority_level = None
    if new_priority_level_id:
        new_priority_level = PriorityLevel.query.get(new_priority_level_id)
        if new_priority_level:
            preview = preview_priority_change(item, new_priority_level, current_user)
    return render_template("partials/_priority_impact.html", item=item, preview=preview, new_priority_level=new_priority_level)


@bp.route("/change/<item_type>/<int:item_id>", methods=["POST"])
@requires_permission("change_priority")
def change(item_type, item_id):
    item = _get_item(item_type, item_id)
    form = PriorityChangeForm()
    form.new_priority_level_id.choices = [
        (p.id, p.name) for p in PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank).all()
    ]

    if not form.validate_on_submit():
        flash("Please fill in all required fields and acknowledge the impact.", "error")
        return redirect(_detail_url(item))

    new_priority_level = PriorityLevel.query.get_or_404(form.new_priority_level_id.data)
    can_override = current_user.has_permission("approve_priority_change") and form.override_blocks.data

    event, preview = commit_priority_change(
        item, new_priority_level, current_user,
        reason=form.reason.data,
        business_justification=form.business_justification.data,
        expected_interruption_minutes=form.expected_interruption_minutes.data,
        is_temporary=form.is_temporary.data,
        resume_date=form.resume_date.data,
        approved_by=current_user if can_override else None,
        acknowledged=form.acknowledged.data,
        override_blocks=can_override,
    )

    if event is None:
        blocking_messages = "; ".join(w["message"] for w in preview["warnings"] if w["level"] == "block")
        flash(f"Priority change blocked: {blocking_messages}", "error")
        return redirect(_detail_url(item))

    db.session.commit()
    flash(f"Priority changed to {new_priority_level.name}.", "success")
    return redirect(_detail_url(item))


@bp.route("/acknowledge/<int:event_id>", methods=["POST"])
@login_required
def acknowledge(event_id):
    event = PriorityEvent.query.get_or_404(event_id)
    if current_user not in event.affected_developers:
        abort(403)
    from app.models.mixins import utcnow
    event.developer_acknowledged_at = utcnow()
    event.developer_acknowledged_by_id = current_user.id
    db.session.commit()
    flash("Acknowledged.", "success")
    return redirect(request.referrer or url_for("dashboard.personal"))

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Chore, ChoreOccurrence, Comment, PriorityLevel, Tag, Team, User
from app.models.priority_event import PriorityEvent
from app.blueprints.chores.forms import (
    ChoreCompleteForm, ChoreEscalateForm, ChoreForm, ChoreReassignForm, ChoreSkipForm,
)
from app.services.activity import get_timeline, log_activity
from app.services.attachments import list_attachments
from app.services.chore_service import (
    complete_occurrence, escalate_occurrence, generate_occurrence_if_due,
    reassign_occurrence, skip_occurrence,
)
from app.services.notifications import notify
from app.services.numbering import next_number
from app.services.permissions import requires_permission

bp = Blueprint("chores", __name__)


def _populate_choices(form):
    form.priority_level_id.choices = [
        (p.id, p.name) for p in PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank).all()
    ]
    users = User.query.filter_by(active=True).order_by(User.full_name).all()
    form.assigned_user_id.choices = [(0, "— None —")] + [(u.id, u.full_name) for u in users]
    form.assigned_team_id.choices = [(0, "— None —")] + [(t.id, t.name) for t in Team.query.order_by(Team.name).all()]


@bp.route("/")
@login_required
def list_view():
    query = Chore.query
    status = request.args.get("status", "active")
    if status:
        query = query.filter_by(status=status)
    priority_id = request.args.get("priority_id", type=int)
    if priority_id:
        query = query.filter_by(priority_level_id=priority_id)
    chores = query.order_by(Chore.next_scheduled_at.asc().nullslast()).all()
    return render_template(
        "chores/list.html", chores=chores, status=status,
        priority_levels=PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank).all(),
    )


@bp.route("/new", methods=["GET", "POST"])
@requires_permission("create_chore")
def create():
    form = ChoreForm()
    _populate_choices(form)

    if form.validate_on_submit():
        cfg = {}
        if form.recurrence_type.data == "specific_day_of_month":
            cfg["day_of_month"] = form.day_of_month.data or 1
        elif form.recurrence_type.data == "specific_weekday":
            cfg["weekday"] = form.weekday.data
        elif form.recurrence_type.data == "custom":
            cfg["interval_days"] = form.interval_days.data or 30

        chore = Chore(
            chore_number="PENDING",
            title=form.title.data,
            description=form.description.data,
            assigned_user_id=form.assigned_user_id.data or None,
            assigned_team_id=form.assigned_team_id.data or None,
            requested_by_id=current_user.id,
            priority_level_id=form.priority_level_id.data,
            recurrence_type=form.recurrence_type.data,
            recurrence_config=cfg,
            due_date=form.due_date.data,
            preferred_time_of_day=form.preferred_time_of_day.data,
            estimated_duration_minutes=form.estimated_duration_minutes.data,
            required_evidence=form.required_evidence.data,
            notes=form.notes.data,
            next_scheduled_at=form.due_date.data or date.today(),
        )
        db.session.add(chore)
        db.session.flush()
        chore.chore_number = next_number(Chore)

        if form.tag_names.data:
            names = [n.strip() for n in form.tag_names.data.split(",") if n.strip()]
            for name in names:
                tag = Tag.query.filter_by(name=name).first() or Tag(name=name)
                chore.tags.append(tag)

        generate_occurrence_if_due(chore, today=chore.next_scheduled_at)
        log_activity("chore", chore.id, "created", f"Chore created by {current_user.full_name}", actor=current_user)
        if chore.assigned_user_id and chore.assigned_user_id != current_user.id:
            notify(
                chore.assigned_user, "assignment", f"You were assigned {chore.title}",
                body=f"{chore.chore_number} · requested by {current_user.full_name}",
                item_type="chore", item_id=chore.id,
            )
        db.session.commit()
        flash(f"Chore {chore.chore_number} created.", "success")
        return redirect(url_for("chores.detail", chore_id=chore.id))

    return render_template("chores/form.html", form=form, chore=None)


@bp.route("/<int:chore_id>")
@login_required
def detail(chore_id):
    chore = Chore.query.get_or_404(chore_id)
    occurrences = chore.occurrences
    pending = [o for o in occurrences if o.status == "pending"]
    timeline = get_timeline("chore", chore.id)
    comments = (
        Comment.query.filter_by(item_type="chore", item_id=chore.id, parent_comment_id=None)
        .order_by(Comment.is_pinned.desc(), Comment.created_at.desc()).all()
    )
    priority_events = (
        PriorityEvent.query.filter_by(item_type="chore", item_id=chore.id)
        .order_by(PriorityEvent.occurred_at.desc()).all()
    )
    users = User.query.filter_by(active=True).order_by(User.full_name).all()
    attachments = list_attachments("chore", chore.id)

    return render_template(
        "chores/detail.html", chore=chore, occurrences=occurrences, pending=pending,
        timeline=timeline, comments=comments, priority_events=priority_events,
        attachments=attachments,
        complete_form=ChoreCompleteForm(), skip_form=ChoreSkipForm(),
        reassign_form=_reassign_form(users), escalate_form=ChoreEscalateForm(),
    )


def _reassign_form(users):
    form = ChoreReassignForm()
    form.new_user_id.choices = [(u.id, u.full_name) for u in users]
    return form


@bp.route("/occurrences/<int:occurrence_id>/complete", methods=["POST"])
@requires_permission("complete_chore")
def complete(occurrence_id):
    occurrence = ChoreOccurrence.query.get_or_404(occurrence_id)
    form = ChoreCompleteForm()
    if form.validate_on_submit():
        complete_occurrence(occurrence, current_user, form.actual_duration_minutes.data, form.notes.data)
        generate_occurrence_if_due(occurrence.chore)
        db.session.commit()
        flash("Chore marked complete.", "success")
    return redirect(url_for("chores.detail", chore_id=occurrence.chore_id))


@bp.route("/occurrences/<int:occurrence_id>/skip", methods=["POST"])
@requires_permission("complete_chore")
def skip(occurrence_id):
    occurrence = ChoreOccurrence.query.get_or_404(occurrence_id)
    form = ChoreSkipForm()
    if form.validate_on_submit():
        skip_occurrence(occurrence, current_user, form.skip_reason.data)
        db.session.commit()
        flash("Occurrence skipped.", "success")
    return redirect(url_for("chores.detail", chore_id=occurrence.chore_id))


@bp.route("/occurrences/<int:occurrence_id>/reassign", methods=["POST"])
@requires_permission("assign_work")
def reassign(occurrence_id):
    occurrence = ChoreOccurrence.query.get_or_404(occurrence_id)
    form = ChoreReassignForm()
    form.new_user_id.choices = [(u.id, u.full_name) for u in User.query.filter_by(active=True).all()]
    if form.validate_on_submit():
        new_user = User.query.get_or_404(form.new_user_id.data)
        reassign_occurrence(occurrence, current_user, new_user)
        notify(
            new_user, "assignment", f"You were assigned {occurrence.chore.title}",
            body=f"Occurrence due {occurrence.occurrence_date.strftime('%b %-d, %Y')}, reassigned by {current_user.full_name}.",
            item_type="chore", item_id=occurrence.chore_id,
        )
        db.session.commit()
        flash(f"Reassigned to {new_user.full_name}.", "success")
    return redirect(url_for("chores.detail", chore_id=occurrence.chore_id))


@bp.route("/occurrences/<int:occurrence_id>/escalate", methods=["POST"])
@requires_permission("complete_chore")
def escalate(occurrence_id):
    occurrence = ChoreOccurrence.query.get_or_404(occurrence_id)
    form = ChoreEscalateForm()
    if form.validate_on_submit():
        escalate_occurrence(occurrence, current_user, form.escalated_reason.data)
        db.session.commit()
        flash("Occurrence escalated.", "success")
    return redirect(url_for("chores.detail", chore_id=occurrence.chore_id))


@bp.route("/<int:chore_id>/pause", methods=["POST"])
@login_required
def toggle_pause(chore_id):
    chore = Chore.query.get_or_404(chore_id)
    chore.status = "paused" if chore.status == "active" else "active"
    log_activity("chore", chore.id, "status_changed", f"Chore {'paused' if chore.status == 'paused' else 'reactivated'}", actor=current_user)
    db.session.commit()
    flash("Chore updated.", "success")
    return redirect(url_for("chores.detail", chore_id=chore.id))

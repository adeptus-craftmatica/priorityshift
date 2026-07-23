from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Comment, Department, Idea, PriorityLevel, Project, ProjectAssignment, ProjectPhase, Tag
from app.models.chore import Chore
from app.blueprints.ideas.forms import ConvertToChoreForm, ConvertToProjectForm, IdeaForm, IdeaStatusForm
from app.services.activity import get_timeline, log_activity
from app.services.attachments import list_attachments
from app.services.numbering import next_number
from app.services.permissions import requires_permission

bp = Blueprint("ideas", __name__)


@bp.route("/")
@login_required
def list_view():
    status = request.args.get("status")
    query = Idea.query
    if status:
        query = query.filter_by(review_status=status)
    else:
        query = query.filter(Idea.review_status.notin_(["converted_to_project", "converted_to_chore", "archived"]))
    ideas = query.order_by(Idea.votes_count.desc(), Idea.created_at.desc()).all()
    return render_template("ideas/list.html", ideas=ideas)


@bp.route("/new", methods=["GET", "POST"])
@requires_permission("create_idea")
def create():
    form = IdeaForm()
    form.department_id.choices = [(0, "— None —")] + [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]

    if form.validate_on_submit():
        idea = Idea(
            idea_number="PENDING",
            title=form.title.data,
            description=form.description.data,
            submitted_by_id=current_user.id,
            submission_date=date.today(),
            department_id=form.department_id.data or None,
            potential_value=form.potential_value.data,
            expected_benefit=form.expected_benefit.data,
            possible_users_affected=form.possible_users_affected.data,
            estimated_effort_hours=form.estimated_effort_hours.data,
            notes=form.notes.data,
        )
        db.session.add(idea)
        db.session.flush()
        idea.idea_number = next_number(Idea)

        if form.tag_names.data:
            for name in [n.strip() for n in form.tag_names.data.split(",") if n.strip()]:
                tag = Tag.query.filter_by(name=name).first() or Tag(name=name)
                idea.tags.append(tag)

        log_activity("idea", idea.id, "created", f"Idea submitted by {current_user.full_name}", actor=current_user)
        db.session.commit()
        flash(f"Idea {idea.idea_number} submitted.", "success")
        return redirect(url_for("ideas.detail", idea_id=idea.id))

    return render_template("ideas/form.html", form=form)


@bp.route("/<int:idea_id>")
@login_required
def detail(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    timeline = get_timeline("idea", idea.id)
    comments = (
        Comment.query.filter_by(item_type="idea", item_id=idea.id, parent_comment_id=None)
        .order_by(Comment.is_pinned.desc(), Comment.created_at.desc()).all()
    )
    status_form = IdeaStatusForm(review_status=idea.review_status)

    convert_project_form = ConvertToProjectForm()
    convert_project_form.priority_level_id.choices = [
        (p.id, p.name) for p in PriorityLevel.query.filter_by(active=True).order_by(PriorityLevel.rank).all()
    ]
    convert_project_form.phase_id.choices = [
        (p.id, p.name) for p in ProjectPhase.query.filter_by(active=True).order_by(ProjectPhase.rank).all()
    ]
    convert_chore_form = ConvertToChoreForm()
    convert_chore_form.priority_level_id.choices = convert_project_form.priority_level_id.choices

    converted_item = None
    if idea.converted_to_type == "project":
        converted_item = Project.query.get(idea.converted_to_id)
    elif idea.converted_to_type == "chore":
        converted_item = Chore.query.get(idea.converted_to_id)

    attachments = list_attachments("idea", idea.id)

    return render_template(
        "ideas/detail.html", idea=idea, timeline=timeline, comments=comments,
        status_form=status_form, convert_project_form=convert_project_form,
        convert_chore_form=convert_chore_form, converted_item=converted_item,
        attachments=attachments,
    )


@bp.route("/<int:idea_id>/status", methods=["POST"])
@requires_permission("review_requests")
def update_status(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    form = IdeaStatusForm()
    if form.validate_on_submit():
        idea.review_status = form.review_status.data
        log_activity("idea", idea.id, "status_changed", f"Status changed to {form.review_status.data.replace('_', ' ')}", actor=current_user)
        db.session.commit()
        flash("Idea status updated.", "success")
    return redirect(url_for("ideas.detail", idea_id=idea.id))


@bp.route("/<int:idea_id>/vote", methods=["POST"])
@login_required
def vote(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    idea.votes_count = (idea.votes_count or 0) + 1
    db.session.commit()
    return redirect(url_for("ideas.detail", idea_id=idea.id))


@bp.route("/<int:idea_id>/convert-to-project", methods=["POST"])
@requires_permission("convert_idea")
def convert_to_project(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    form = ConvertToProjectForm()
    form.priority_level_id.choices = [(p.id, p.name) for p in PriorityLevel.query.filter_by(active=True).all()]
    form.phase_id.choices = [(p.id, p.name) for p in ProjectPhase.query.filter_by(active=True).all()]

    if form.validate_on_submit():
        project = Project(
            project_number="PENDING",
            title=idea.title,
            description=idea.description,
            priority_level_id=form.priority_level_id.data,
            original_priority_level_id=form.priority_level_id.data,
            phase_id=form.phase_id.data,
            requested_by_id=idea.submitted_by_id,
            requesting_department_id=idea.department_id,
            date_requested=date.today(),
            target_deadline=form.target_deadline.data,
            original_deadline=form.target_deadline.data,
            estimated_effort_hours=idea.estimated_effort_hours,
            origin_idea_id=idea.id,
            last_activity_at=db.func.now(),
        )
        db.session.add(project)
        db.session.flush()
        project.project_number = next_number(Project)
        if idea.submitted_by_id:
            db.session.add(ProjectAssignment(project_id=project.id, user_id=idea.submitted_by_id))

        idea.converted_to_type = "project"
        idea.converted_to_id = project.id
        idea.review_status = "converted_to_project"

        log_activity("idea", idea.id, "converted", f"Converted to project {project.project_number}", actor=current_user)
        log_activity("project", project.id, "created", f"Created from idea {idea.idea_number}", actor=current_user)
        db.session.commit()
        flash(f"Converted to project {project.project_number}.", "success")
        return redirect(url_for("projects.detail", project_id=project.id))

    flash("Couldn't convert — check the form.", "error")
    return redirect(url_for("ideas.detail", idea_id=idea.id))


@bp.route("/<int:idea_id>/convert-to-chore", methods=["POST"])
@requires_permission("convert_idea")
def convert_to_chore(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    form = ConvertToChoreForm()
    form.priority_level_id.choices = [(p.id, p.name) for p in PriorityLevel.query.filter_by(active=True).all()]

    if form.validate_on_submit():
        chore = Chore(
            chore_number="PENDING",
            title=idea.title,
            description=idea.description,
            assigned_user_id=idea.submitted_by_id,
            requested_by_id=idea.submitted_by_id,
            priority_level_id=form.priority_level_id.data,
            recurrence_type=form.recurrence_type.data,
            recurrence_config={},
            due_date=form.due_date.data,
            next_scheduled_at=form.due_date.data or date.today(),
            origin_idea_id=idea.id,
        )
        db.session.add(chore)
        db.session.flush()
        chore.chore_number = next_number(Chore)

        idea.converted_to_type = "chore"
        idea.converted_to_id = chore.id
        idea.review_status = "converted_to_chore"

        log_activity("idea", idea.id, "converted", f"Converted to chore {chore.chore_number}", actor=current_user)
        log_activity("chore", chore.id, "created", f"Created from idea {idea.idea_number}", actor=current_user)
        db.session.commit()
        flash(f"Converted to chore {chore.chore_number}.", "success")
        return redirect(url_for("chores.detail", chore_id=chore.id))

    flash("Couldn't convert — check the form.", "error")
    return redirect(url_for("ideas.detail", idea_id=idea.id))

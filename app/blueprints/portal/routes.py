"""The client-facing portal — a deliberately narrow view for external
client contacts (User.client_id is set). Never reuses the internal
Projects blueprint's queries: this view hand-picks which fields reach an
external user (no financial classification, no internal notes/risks/
roadblocks, no priority-change reasoning or interruption history) rather
than filtering an internal serializer, so there's no risk of a future
internal field leaking through by accident."""

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.blueprints.portal.forms import PortalCommentForm
from app.models import Comment, Project
from app.services.activity import log_activity

bp = Blueprint("portal", __name__)


def _require_client_contact():
    if not current_user.is_client_contact:
        abort(404)


@bp.route("/")
@login_required
def dashboard():
    _require_client_contact()
    projects = (
        Project.query.filter_by(client_id=current_user.client_id, is_archived=False)
        .order_by(Project.target_deadline.is_(None), Project.target_deadline)
        .all()
    )
    return render_template("portal/dashboard.html", projects=projects)


@bp.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    _require_client_contact()
    project = Project.query.get_or_404(project_id)
    if project.client_id != current_user.client_id:
        abort(404)
    comments = (
        Comment.query.filter_by(item_type="project", item_id=project.id, client_visible=True)
        .order_by(Comment.created_at.asc())
        .all()
    )
    return render_template(
        "portal/project_detail.html", project=project, comments=comments, form=PortalCommentForm(),
    )


@bp.route("/projects/<int:project_id>/comments", methods=["POST"])
@login_required
def add_comment(project_id):
    _require_client_contact()
    project = Project.query.get_or_404(project_id)
    if project.client_id != current_user.client_id:
        abort(404)

    form = PortalCommentForm()
    if form.validate_on_submit():
        comment = Comment(
            item_type="project", item_id=project.id, author_id=current_user.id,
            body=form.body.data, client_visible=True,
        )
        db.session.add(comment)
        log_activity("project", project.id, "comment_added", f"{current_user.full_name} (client) commented", actor=current_user)
        db.session.commit()
    return redirect(url_for("portal.project_detail", project_id=project.id))

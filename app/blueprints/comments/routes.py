import re

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Comment, User
from app.blueprints.comments.forms import CommentForm
from app.services.activity import log_activity
from app.services.notifications import get_assignees_for_item, get_item_object, notify, notify_many
from app.services.permissions import requires_permission

MENTION_PATTERN = re.compile(r"@([a-zA-Z0-9_.]+)")

bp = Blueprint("comments", __name__)


def _list_partial(item_type, item_id):
    comments = (
        Comment.query.filter_by(item_type=item_type, item_id=item_id, parent_comment_id=None)
        .order_by(Comment.is_pinned.desc(), Comment.created_at.desc())
        .all()
    )
    return render_template("partials/_comment_list.html", comments=comments, item_type=item_type, item_id=item_id)


@bp.route("/<item_type>/<int:item_id>")
@login_required
def list_comments(item_type, item_id):
    return _list_partial(item_type, item_id)


@bp.route("/<item_type>/<int:item_id>", methods=["POST"])
@requires_permission("comment")
def add_comment(item_type, item_id):
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(
            item_type=item_type, item_id=item_id, author_id=current_user.id,
            body=form.body.data, is_decision=form.is_decision.data, is_blocker=form.is_blocker.data,
            client_visible=form.client_visible.data,
            parent_comment_id=int(form.parent_comment_id.data) if form.parent_comment_id.data else None,
        )
        db.session.add(comment)
        log_activity(item_type, item_id, "comment_added", f"{current_user.full_name} commented", actor=current_user)
        _notify_for_comment(item_type, item_id, comment, form)
        db.session.commit()
    return _list_partial(item_type, item_id)


def _notify_for_comment(item_type, item_id, comment, form):
    item = get_item_object(item_type, item_id)
    title = getattr(item, "title", None) if item else None
    if not title:
        return

    mentioned_usernames = set(MENTION_PATTERN.findall(comment.body))
    if mentioned_usernames:
        mentioned_users = User.query.filter(
            User.username.in_(mentioned_usernames), User.active.is_(True),
        ).all()
        for user in mentioned_users:
            if user.id != current_user.id:
                notify(
                    user, "comment_mention", f"{current_user.full_name} mentioned you on {title}",
                    body=comment.body[:200], item_type=item_type, item_id=item_id,
                )

    recipients = [u for u in get_assignees_for_item(item) if u.id != current_user.id]
    if form.is_decision.data and recipients:
        notify_many(
            recipients, "decision", f"New decision recorded on {title}",
            body=comment.body[:200], item_type=item_type, item_id=item_id,
        )
    if form.is_blocker.data and recipients:
        notify_many(
            recipients, "new_blocker", f"New blocker reported on {title}",
            body=comment.body[:200], item_type=item_type, item_id=item_id,
        )


@bp.route("/<int:comment_id>/pin", methods=["POST"])
@login_required
def toggle_pin(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.is_pinned = not comment.is_pinned
    db.session.commit()
    return _list_partial(comment.item_type, comment.item_id)


@bp.route("/<int:comment_id>/edit", methods=["POST"])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author_id != current_user.id:
        abort(403)
    from app.models.mixins import utcnow
    comment.body = request.form.get("body", comment.body)
    comment.edited_at = utcnow()
    db.session.commit()
    return _list_partial(comment.item_type, comment.item_id)

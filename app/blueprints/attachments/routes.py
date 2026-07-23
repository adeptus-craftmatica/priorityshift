from flask import Blueprint, abort, flash, redirect, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Attachment
from app.services.activity import log_activity
from app.services.attachments import VALID_ITEM_TYPES, UploadError, delete_attachment, save_attachment

bp = Blueprint("attachments", __name__)


def _detail_url(item_type, item_id):
    if item_type == "project":
        return url_for("projects.detail", project_id=item_id)
    if item_type == "chore":
        return url_for("chores.detail", chore_id=item_id)
    return url_for("ideas.detail", idea_id=item_id)


@bp.route("/<item_type>/<int:item_id>", methods=["POST"])
@login_required
def upload(item_type, item_id):
    if item_type not in VALID_ITEM_TYPES:
        abort(404)
    try:
        attachment = save_attachment(request.files.get("file"), item_type, item_id, current_user)
        log_activity(
            item_type, item_id, "file_uploaded",
            f"{current_user.full_name} uploaded {attachment.filename}", actor=current_user,
        )
        db.session.commit()
        flash(f"Uploaded {attachment.filename}.", "success")
    except UploadError as exc:
        flash(str(exc), "error")
    return redirect(_detail_url(item_type, item_id) + "#attachments")


@bp.route("/download/<int:attachment_id>")
@login_required
def download(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    return send_file(attachment.stored_path, download_name=attachment.filename, as_attachment=True)


@bp.route("/<int:attachment_id>/delete", methods=["POST"])
@login_required
def delete(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    if attachment.uploaded_by_id != current_user.id and not current_user.has_permission("manage_users"):
        abort(403)
    item_type, item_id, filename = attachment.item_type, attachment.item_id, attachment.filename
    delete_attachment(attachment)
    log_activity(item_type, item_id, "file_removed", f"{current_user.full_name} removed {filename}", actor=current_user)
    db.session.commit()
    flash("Attachment removed.", "success")
    return redirect(_detail_url(item_type, item_id) + "#attachments")

import os
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Attachment

VALID_ITEM_TYPES = {"project", "chore", "idea"}


class UploadError(Exception):
    pass


def _allowed(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]


def save_attachment(file_storage, item_type, item_id, uploaded_by):
    if item_type not in VALID_ITEM_TYPES:
        raise UploadError("Unknown item type.")
    if not file_storage or not file_storage.filename:
        raise UploadError("Choose a file first.")

    original_name = secure_filename(file_storage.filename)
    if not original_name:
        raise UploadError("That filename isn't valid.")
    if not _allowed(original_name):
        raise UploadError(f"File type not allowed: {original_name}")

    item_dir = Path(current_app.config["UPLOAD_FOLDER"]) / item_type / str(item_id)
    item_dir.mkdir(parents=True, exist_ok=True)

    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    stored_path = item_dir / stored_name
    file_storage.save(stored_path)

    attachment = Attachment(
        item_type=item_type,
        item_id=item_id,
        filename=original_name,
        stored_path=str(stored_path),
        content_type=file_storage.content_type,
        size_bytes=stored_path.stat().st_size,
        uploaded_by_id=uploaded_by.id if uploaded_by else None,
    )
    db.session.add(attachment)
    return attachment


def delete_attachment(attachment):
    try:
        os.remove(attachment.stored_path)
    except OSError:
        pass
    db.session.delete(attachment)


def list_attachments(item_type, item_id):
    return (
        Attachment.query.filter_by(item_type=item_type, item_id=item_id)
        .order_by(Attachment.uploaded_at.desc())
        .all()
    )

from app.extensions import db
from app.models import ActivityLog


def log_activity(item_type, item_id, event_type, description, actor=None, metadata=None):
    """Append-only activity timeline entry. Never update or delete rows from
    here — corrections should call this again with event_type='correction'."""
    entry = ActivityLog(
        item_type=item_type,
        item_id=item_id,
        actor_id=actor.id if actor else None,
        event_type=event_type,
        description=description,
        event_metadata=metadata or {},
    )
    db.session.add(entry)
    return entry


def get_timeline(item_type, item_id):
    return (
        ActivityLog.query.filter_by(item_type=item_type, item_id=item_id)
        .order_by(ActivityLog.created_at.desc())
        .all()
    )

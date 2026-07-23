"""Account lifecycle changes (lock/unlock, archive/unarchive) — shared by
the web admin blueprint and the desktop Control Panel so neither surface
can change a user's standing without leaving an audit trail. Every change
is logged via the same insert-only ActivityLog used elsewhere in the app
(item_type="user"), never just silently flipped."""

from app.extensions import db
from app.services.activity import log_activity


def set_active(user, active, actor=None, reason=None):
    """Lock out (active=False) or unlock (active=True) — a temporary,
    reversible suspension. Does not touch is_archived."""
    if user.active == active:
        return None
    user.active = active
    event_type = "unlocked" if active else "locked"
    description = f"{user.full_name} {'unlocked' if active else 'locked out'}"
    if reason:
        description += f" — {reason}"
    return log_activity("user", user.id, event_type, description, actor=actor, metadata={"reason": reason})


def archive_user(user, actor=None, reason=None):
    """Marks a user as permanently done (e.g. left the company) — hidden
    from default active-user lists and unable to log in, but never deleted
    so historical records they authored stay intact and attributable."""
    if user.is_archived:
        return None
    user.is_archived = True
    user.active = False
    description = f"{user.full_name} archived"
    if reason:
        description += f" — {reason}"
    return log_activity("user", user.id, "archived", description, actor=actor, metadata={"reason": reason})


def unarchive_user(user, actor=None, reason=None):
    """Restores an archived user to normal active standing."""
    if not user.is_archived:
        return None
    user.is_archived = False
    user.active = True
    description = f"{user.full_name} restored from archive"
    if reason:
        description += f" — {reason}"
    return log_activity("user", user.id, "unarchived", description, actor=actor, metadata={"reason": reason})


def get_user_history(user):
    from app.models import ActivityLog
    return (
        ActivityLog.query.filter_by(item_type="user", item_id=user.id)
        .order_by(ActivityLog.created_at.desc())
        .all()
    )

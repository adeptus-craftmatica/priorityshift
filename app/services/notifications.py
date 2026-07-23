"""Central place that creates Notification rows. Keeping this as one
choke point (rather than constructing Notification() ad hoc all over the
codebase) makes it easy to see every event type that can notify someone,
and to add de-duplication in one place."""

from datetime import date, timedelta

from app.extensions import db
from app.models import Chore, Idea, Notification, Project
from app.services.delivery import deliver_notification


def notify(user, type_, title, body=None, item_type=None, item_id=None, link_url=None):
    if user is None:
        return None
    notification = Notification(
        user_id=user.id, type=type_, title=title, body=body,
        item_type=item_type, item_id=item_id, link_url=link_url,
    )
    notification.user = user  # avoids a lazy-load query when delivery reads notification.user below
    db.session.add(notification)
    deliver_notification(notification)
    return notification


def notify_many(users, type_, title, body=None, item_type=None, item_id=None):
    for user in users:
        notify(user, type_, title, body=body, item_type=item_type, item_id=item_id)


def get_item_object(item_type, item_id):
    model = {"project": Project, "chore": Chore, "idea": Idea}.get(item_type)
    return model.query.get(item_id) if model else None


def get_assignees_for_item(item):
    """Works for any of the three item types, unlike priority_service's
    version which only needs to handle project/chore."""
    if item.item_type == "project":
        return [a.user for a in item.assignments]
    if item.item_type == "chore":
        if item.assigned_user:
            return [item.assigned_user]
        if item.assigned_team:
            return list(item.assigned_team.users)
        return []
    if item.item_type == "idea":
        return [item.submitted_by] if item.submitted_by else []
    return []


def _recently_notified(user_id, type_, item_type, item_id, within_hours=20):
    existing = (
        Notification.query.filter_by(user_id=user_id, type=type_, item_type=item_type, item_id=item_id)
        .order_by(Notification.created_at.desc())
        .first()
    )
    if existing is None:
        return False
    from app.models.mixins import utcnow
    return (utcnow().replace(tzinfo=None) - existing.created_at) < timedelta(hours=within_hours)


def generate_due_reminders_for_user(user, queue):
    """Opportunistic reminders for one user's own queue — called from their
    dashboard load rather than a background scheduler, so it only ever
    touches the person actually looking at the app right now. De-duplicated
    so refreshing the page repeatedly doesn't spam the same reminder."""
    today = date.today()
    created = []

    for entry in queue:
        due = entry["due_date"]
        if not due:
            continue
        obj = entry["obj"]

        if due < today and not _recently_notified(user.id, "overdue", entry["type"], entry["id"]):
            created.append(notify(
                user, "overdue", f"{entry['number']} is overdue",
                body=f"{entry['title']} was due {due.strftime('%b %-d, %Y')}.",
                item_type=entry["type"], item_id=entry["id"],
            ))
        elif today <= due <= today + timedelta(days=3) and not _recently_notified(user.id, "deadline_upcoming", entry["type"], entry["id"]):
            created.append(notify(
                user, "deadline_upcoming", f"{entry['number']} is due soon",
                body=f"{entry['title']} is due {due.strftime('%b %-d, %Y')}.",
                item_type=entry["type"], item_id=entry["id"],
            ))

    return [c for c in created if c is not None]

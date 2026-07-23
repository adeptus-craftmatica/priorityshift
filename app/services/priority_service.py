"""The reprioritization engine: preview the impact of a priority change
before it happens, then commit it as a permanent, insert-only audit
record (PriorityEvent). Nothing here ever overwrites a previous priority
value without preserving it."""

import math
from datetime import timedelta

from app.extensions import db
from app.models import Chore, Notification, PriorityEvent, PriorityLevel, Project, WorkflowRule
from app.services.activity import log_activity
from app.services.deadline_service import revise_deadline
from app.services.priority_queue import get_priority_queue_for_user


def get_assignees(item):
    if item.item_type == "project":
        return [a.user for a in item.assignments]
    if item.item_type == "chore":
        if item.assigned_user:
            return [item.assigned_user]
        if item.assigned_team:
            return list(item.assigned_team.users)
    return []


def _critical_rank():
    critical = PriorityLevel.query.filter_by(name="Critical").first()
    return critical.rank if critical else 1


def check_workflow_rules(item, new_priority_level, assignees, requester):
    """Returns a list of {rule_type, level ('warning'|'block'), message}.
    'block' can only be bypassed by a requester holding
    approve_priority_change (enforced by the caller, not here)."""
    warnings = []
    rules = WorkflowRule.query.filter_by(active=True).all()
    critical_rank = _critical_rank()

    for rule in rules:
        if rule.rule_type == "max_critical_per_developer" and new_priority_level.rank <= critical_rank:
            threshold = rule.threshold or 2
            for user in assignees:
                current = [
                    e for e in get_priority_queue_for_user(user)
                    if e["type"] == "project" and e["priority_rank"] <= critical_rank
                    and not (e["type"] == item.item_type and e["id"] == item.id)
                ]
                if len(current) + 1 > threshold:
                    warnings.append({
                        "rule_type": rule.rule_type,
                        "level": "block",
                        "message": (
                            f"{user.full_name} would have {len(current) + 1} Critical projects, "
                            f"above the limit of {threshold}."
                        ),
                    })

        elif rule.rule_type == "require_exec_approval_for_critical" and new_priority_level.rank <= critical_rank:
            if not requester or not requester.has_permission("approve_priority_change"):
                warnings.append({
                    "rule_type": rule.rule_type,
                    "level": "block",
                    "message": "Raising an item to Critical requires executive approval.",
                })

    return warnings


def preview_priority_change(item, new_priority_level, requester):
    """What would happen if we applied this change right now — without
    writing anything."""
    assignees = get_assignees(item)
    displaced = []

    for user in assignees:
        queue = get_priority_queue_for_user(user)
        others = [e for e in queue if not (e["type"] == item.item_type and e["id"] == item.id)]
        if others:
            current_top = others[0]
            if new_priority_level.rank < current_top["priority_rank"]:
                displaced.append({"user": user, "item": current_top})

    warnings = check_workflow_rules(item, new_priority_level, assignees, requester)

    projected_deadline_shift = None
    if item.item_type == "project" and item.target_deadline and displaced:
        projected_deadline_shift = (
            "Deadlines for displaced work may need to move — review before confirming."
        )

    return {
        "assignees": assignees,
        "displaced": displaced,
        "warnings": warnings,
        "is_increase": new_priority_level.rank < item.priority_level.rank,
        "projected_deadline_shift": projected_deadline_shift,
    }


def commit_priority_change(
    item, new_priority_level, requester, reason, business_justification="",
    expected_interruption_minutes=None, is_temporary=False, resume_date=None,
    approved_by=None, acknowledged=False, override_blocks=False,
):
    preview = preview_priority_change(item, new_priority_level, requester)
    blocking = [w for w in preview["warnings"] if w["level"] == "block"]
    if blocking and not override_blocks:
        return None, preview

    previous_priority_level = item.priority_level

    event = PriorityEvent(
        item_type=item.item_type,
        item_id=item.id,
        requested_by_id=requester.id if requester else None,
        approved_by_id=approved_by.id if approved_by else None,
        previous_priority_level_id=previous_priority_level.id if previous_priority_level else None,
        new_priority_level_id=new_priority_level.id,
        reason=reason,
        business_justification=business_justification,
        expected_interruption_minutes=expected_interruption_minutes,
        displaced_summary="; ".join(
            f"{d['item']['number']} ({d['user'].full_name})" for d in preview["displaced"]
        ) or None,
        estimated_impact=preview["projected_deadline_shift"],
        is_temporary=is_temporary,
        resume_date=resume_date,
    )
    if acknowledged:
        event.developer_acknowledged_at = db.func.now()
        event.developer_acknowledged_by_id = requester.id if requester else None
    event.affected_developers = preview["assignees"]
    db.session.add(event)
    db.session.flush()

    item.priority_level_id = new_priority_level.id
    item.reprioritization_count = (item.reprioritization_count or 0) + 1
    if hasattr(item, "last_activity_at"):
        item.last_activity_at = db.func.now()

    log_activity(
        item.item_type, item.id, "priority_changed",
        f"Priority changed from {previous_priority_level.name if previous_priority_level else 'none'} "
        f"to {new_priority_level.name} — {reason}",
        actor=requester,
        metadata={"priority_event_id": event.id, "reason": reason},
    )

    if expected_interruption_minutes and item.item_type == "project" and item.target_deadline:
        hours_lost = expected_interruption_minutes / 60.0
        days_lost = max(1, math.ceil(hours_lost / 8))
        new_deadline = item.target_deadline + timedelta(days=days_lost)
        revise_deadline(
            item, new_deadline,
            reason=f"Priority interruption ({new_priority_level.name}): {reason}",
            changed_by=requester, priority_event=event, estimated_hours_lost=hours_lost,
            check_approval=False,
        )

    for user in preview["assignees"]:
        db.session.add(Notification(
            user_id=user.id,
            type="priority_change",
            title=f"Priority changed on {item.title}",
            body=f"New priority: {new_priority_level.name}. Reason: {reason}",
            item_type=item.item_type,
            item_id=item.id,
        ))

    for d in preview["displaced"]:
        db.session.add(Notification(
            user_id=d["user"].id,
            type="work_paused",
            title=f"{d['item']['number']} may be paused",
            body=f"{item.title} was just raised to {new_priority_level.name} and may take priority.",
            item_type=d["item"]["type"],
            item_id=d["item"]["id"],
        ))

    return event, preview

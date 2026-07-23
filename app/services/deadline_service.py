from datetime import date, timedelta

from app.extensions import db
from app.models import DeadlineRevision, WorkflowRule
from app.services.activity import log_activity


def deadline_push_requires_approval(project, previous_deadline, new_deadline, requester):
    """Mirrors the priority-change workflow's guardrail pattern: an
    admin-configurable rule (rather than a hardcoded threshold) decides
    when a deadline push is big enough to need sign-off, and anyone
    holding approve_priority_change can push deadlines directly."""
    if not previous_deadline or not new_deadline:
        return False
    if requester and requester.has_permission("approve_priority_change"):
        return False
    push_days = (new_deadline - previous_deadline).days
    if push_days <= 0:
        return False
    rule = WorkflowRule.query.filter_by(rule_type="require_approval_for_deadline_push", active=True).first()
    if not rule:
        return False
    threshold = rule.threshold or 5
    return push_days > threshold


def get_projected_completion(project):
    """Projects a completion date from remaining effort, each assignee's
    capacity split across their active projects, and this project's own
    history of interruption drag — so "on paper" deadlines can be checked
    against what the numbers actually predict."""
    current_deadline = project.revised_deadline or project.target_deadline

    if not project.estimated_effort_hours:
        return {
            "insufficient_data": True,
            "reason": "No estimated effort hours set for this project.",
            "current_deadline": current_deadline,
        }

    remaining_hours = project.estimated_effort_hours * (1 - (project.percent_complete or 0) / 100)
    if remaining_hours <= 0:
        return {
            "insufficient_data": False,
            "remaining_hours": 0,
            "projected_completion": date.today(),
            "current_deadline": current_deadline,
            "days_variance": (
                (date.today() - current_deadline).days if current_deadline else None
            ),
            "at_risk": False,
        }

    from app.services.priority_queue import get_priority_queue_for_user

    assignees = [a.user for a in project.assignments] or ([project.owner] if project.owner else [])
    if not assignees:
        return {
            "insufficient_data": True,
            "reason": "No one is assigned to this project yet.",
            "current_deadline": current_deadline,
        }

    team_hours_per_week = 0.0
    for user in assignees:
        active_project_count = sum(
            1 for e in get_priority_queue_for_user(user) if e["type"] == "project"
        ) or 1
        team_hours_per_week += (user.capacity_hours_per_week or 0.0) / active_project_count

    weeks_elapsed = None
    interruption_hours_per_week = 0.0
    if project.date_started:
        weeks_elapsed = max(1.0, (date.today() - project.date_started).days / 7.0)
        interruption_hours_per_week = (project.total_interruption_minutes or 0) / 60.0 / weeks_elapsed

    effective_hours_per_week = max(0.1, team_hours_per_week - interruption_hours_per_week)
    weeks_needed = remaining_hours / effective_hours_per_week
    projected_completion = date.today() + timedelta(weeks=weeks_needed)

    days_variance = (projected_completion - current_deadline).days if current_deadline else None

    return {
        "insufficient_data": False,
        "remaining_hours": round(remaining_hours, 1),
        "effective_hours_per_week": round(effective_hours_per_week, 1),
        "interruption_hours_per_week": round(interruption_hours_per_week, 1),
        "projected_completion": projected_completion,
        "current_deadline": current_deadline,
        "days_variance": days_variance,
        "at_risk": bool(days_variance and days_variance > 0),
    }


def revise_deadline(project, new_deadline, reason, changed_by=None, priority_event=None,
                     approved_by=None, estimated_hours_lost=None, notify_assignees=True,
                     check_approval=True):
    previous = project.revised_deadline or project.target_deadline

    if check_approval and deadline_push_requires_approval(project, previous, new_deadline, changed_by):
        revision = DeadlineRevision(
            project_id=project.id,
            previous_deadline=previous,
            new_deadline=new_deadline,
            reason=reason,
            priority_event_id=priority_event.id if priority_event else None,
            changed_by_id=changed_by.id if changed_by else None,
            estimated_hours_lost=estimated_hours_lost,
            status="pending",
        )
        db.session.add(revision)
        db.session.flush()

        log_activity(
            "project", project.id, "deadline_change_requested",
            f"Deadline change requested: {previous or 'unset'} → {new_deadline} — {reason}",
            actor=changed_by,
            metadata={"revision_id": revision.id},
        )

        if notify_assignees:
            from app.models import User
            from app.services.notifications import notify_many
            approvers = [u for u in User.query.filter_by(active=True).all() if u.has_permission("approve_priority_change")]
            requester_name = changed_by.full_name if changed_by else "Someone"
            notify_many(
                approvers, "approval_request", f"Deadline change needs approval: {project.title}",
                body=f"{requester_name} requested moving the deadline from {previous or 'unset'} "
                     f"to {new_deadline}. Reason: {reason}",
                item_type="project", item_id=project.id,
            )
        return revision

    revision = DeadlineRevision(
        project_id=project.id,
        previous_deadline=previous,
        new_deadline=new_deadline,
        reason=reason,
        priority_event_id=priority_event.id if priority_event else None,
        changed_by_id=changed_by.id if changed_by else None,
        approved_by_id=approved_by.id if approved_by else None,
        estimated_hours_lost=estimated_hours_lost,
        status="approved",
        decided_at=db.func.now() if approved_by else None,
    )
    db.session.add(revision)

    # Both fields are kept in sync deliberately: dashboards, priority queues,
    # and list views all sort/filter on target_deadline, so if only
    # revised_deadline changed here, a priority-driven deadline push would
    # never actually show up anywhere except the deadline-history tab.
    project.target_deadline = new_deadline
    project.revised_deadline = new_deadline
    project.deadline_revision_count = (project.deadline_revision_count or 0) + 1

    log_activity(
        "project", project.id, "deadline_changed",
        f"Deadline moved from {previous or 'unset'} to {new_deadline} — {reason}",
        actor=changed_by,
        metadata={"previous": str(previous) if previous else None, "new": str(new_deadline)},
    )

    if notify_assignees:
        from app.services.notifications import notify_many
        assignees = [a.user for a in project.assignments]
        notify_many(
            assignees, "deadline_change", f"Deadline for {project.title} changed",
            body=f"New deadline: {new_deadline.strftime('%b %-d, %Y')}. {reason}",
            item_type="project", item_id=project.id,
        )

    return revision


def approve_deadline_revision(revision, approved_by, notes=None):
    project = revision.project
    previous = revision.previous_deadline

    project.target_deadline = revision.new_deadline
    project.revised_deadline = revision.new_deadline
    project.deadline_revision_count = (project.deadline_revision_count or 0) + 1

    revision.status = "approved"
    revision.approved_by_id = approved_by.id if approved_by else None
    revision.decision_notes = notes
    revision.decided_at = db.func.now()

    log_activity(
        "project", project.id, "deadline_changed",
        f"Deadline moved from {previous or 'unset'} to {revision.new_deadline} — {revision.reason} "
        f"(approved by {approved_by.full_name if approved_by else 'system'})",
        actor=approved_by,
        metadata={"revision_id": revision.id},
    )

    from app.services.notifications import notify, notify_many
    assignees = [a.user for a in project.assignments]
    notify_many(
        assignees, "deadline_change", f"Deadline for {project.title} changed",
        body=f"New deadline: {revision.new_deadline.strftime('%b %-d, %Y')}. {revision.reason}",
        item_type="project", item_id=project.id,
    )
    if revision.changed_by and revision.changed_by not in assignees:
        notify(
            revision.changed_by, "deadline_change", f"Your deadline change for {project.title} was approved",
            body=notes or "Approved.", item_type="project", item_id=project.id,
        )
    return revision


def reject_deadline_revision(revision, rejected_by, notes=None):
    revision.status = "rejected"
    revision.approved_by_id = rejected_by.id if rejected_by else None
    revision.decision_notes = notes
    revision.decided_at = db.func.now()

    log_activity(
        "project", revision.project_id, "deadline_change_rejected",
        f"Deadline change request ({revision.previous_deadline or 'unset'} to {revision.new_deadline}) "
        f"was rejected. {notes or ''}",
        actor=rejected_by,
        metadata={"revision_id": revision.id},
    )

    from app.services.notifications import notify
    if revision.changed_by:
        notify(
            revision.changed_by, "decision", f"Deadline change rejected: {revision.project.title}",
            body=notes or "Your requested deadline change was not approved.",
            item_type="project", item_id=revision.project_id,
        )
    return revision


def project_deadline_summary(project):
    revisions = (
        DeadlineRevision.query.filter_by(project_id=project.id)
        .order_by(DeadlineRevision.changed_at.desc())
        .all()
    )
    applied = [r for r in revisions if r.status == "approved"]
    pending = [r for r in revisions if r.status == "pending"]
    current = project.revised_deadline or project.target_deadline
    total_days_moved = None
    if project.original_deadline and current:
        total_days_moved = (current - project.original_deadline).days
    return {
        "original_deadline": project.original_deadline,
        "current_deadline": current,
        "revisions": revisions,
        "revision_count": len(applied),
        "pending_revisions": pending,
        "total_days_moved": total_days_moved,
        "projection": get_projected_completion(project),
    }

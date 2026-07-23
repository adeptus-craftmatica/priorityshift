"""Turns the audit trail into the evidence-based reports the platform
promises: not just "what happened" but "why deadlines moved and who asked
for it," computed straight from PriorityEvent/DeadlineRevision/Interruption/
TimeEntry — never hand-written after the fact."""

from collections import Counter
from datetime import date, timedelta

from app.models import (
    Chore, ChoreOccurrence, DeadlineRevision, Department, Interruption, PriorityEvent,
    Project, TimeEntry, User,
)
from app.services.priority_queue import get_committed_hours_for_user


def priority_change_report(start=None, end=None):
    query = PriorityEvent.query
    if start:
        query = query.filter(PriorityEvent.occurred_at >= start)
    if end:
        query = query.filter(PriorityEvent.occurred_at <= end)
    events = query.all()

    by_project = Counter()
    by_requester = Counter()
    by_department = Counter()

    for e in events:
        by_project[f"{e.item_type}#{e.item_id}"] += 1
        if e.requested_by:
            by_requester[e.requested_by.full_name] += 1
            for dept in e.requested_by.departments:
                by_department[dept.name] += 1

    project_count = Project.query.count() or 1
    avg_per_project = round(sum(by_project.values()) / project_count, 2)

    top_reprioritized = (
        Project.query.filter(Project.reprioritization_count > 0)
        .order_by(Project.reprioritization_count.desc()).limit(10).all()
    )

    return {
        "events": events,
        "total_changes": len(events),
        "by_project": by_project.most_common(10),
        "by_requester": by_requester.most_common(10),
        "by_department": by_department.most_common(10),
        "avg_per_project": avg_per_project,
        "top_reprioritized": top_reprioritized,
    }


def deadline_impact_report(start=None, end=None):
    query = DeadlineRevision.query
    if start:
        query = query.filter(DeadlineRevision.changed_at >= start)
    if end:
        query = query.filter(DeadlineRevision.changed_at <= end)
    revisions = query.all()

    total_hours_lost = sum(r.estimated_hours_lost or 0 for r in revisions)

    today = date.today()
    completed_late = []
    for p in Project.query.filter(Project.original_deadline.isnot(None)).all():
        current = p.revised_deadline or p.target_deadline
        if current and p.original_deadline and current > p.original_deadline:
            completed_late.append(p)

    by_department = Counter()
    for r in revisions:
        if r.project and r.project.requesting_department:
            by_department[r.project.requesting_department.name] += 1

    return {
        "revisions": revisions,
        "total_revisions": len(revisions),
        "total_hours_lost": round(total_hours_lost, 1),
        "projects_with_moved_deadlines": completed_late,
        "by_department": by_department.most_common(10),
    }


def workload_report(start=None, end=None):
    query = TimeEntry.query
    if start:
        query = query.filter(TimeEntry.entry_date >= start)
    if end:
        query = query.filter(TimeEntry.entry_date <= end)
    entries = query.all()

    by_developer = Counter()
    planned_hours = 0.0
    unplanned_hours = 0.0
    project_hours = 0.0
    chore_hours = 0.0

    for t in entries:
        by_developer[t.user.full_name if t.user else "Unknown"] += t.hours
        if t.category == "planned":
            planned_hours += t.hours
        else:
            unplanned_hours += t.hours
        if t.item_type == "project":
            project_hours += t.hours
        else:
            chore_hours += t.hours

    client_hours = 0.0
    internal_hours = 0.0
    paid_hours = 0.0
    unpaid_hours = 0.0
    for t in entries:
        if t.item_type == "project":
            project = Project.query.get(t.item_id)
            if project:
                if project.is_client:
                    client_hours += t.hours
                else:
                    internal_hours += t.hours
                if project.is_paid:
                    paid_hours += t.hours
                else:
                    unpaid_hours += t.hours

    capacity_utilization = []
    for user in User.query.filter_by(active=True).order_by(User.full_name).all():
        committed = get_committed_hours_for_user(user)
        capacity = user.capacity_hours_per_week or 0
        utilization_pct = round(committed / capacity * 100) if capacity else None
        if committed or capacity:
            capacity_utilization.append({
                "user": user,
                "committed_hours": round(committed, 1),
                "capacity_hours": capacity,
                "utilization_pct": utilization_pct,
                "over_capacity": bool(utilization_pct and utilization_pct > 100),
            })
    capacity_utilization.sort(key=lambda row: row["utilization_pct"] or 0, reverse=True)

    return {
        "by_developer": by_developer.most_common(20),
        "planned_hours": round(planned_hours, 1),
        "unplanned_hours": round(unplanned_hours, 1),
        "project_hours": round(project_hours, 1),
        "chore_hours": round(chore_hours, 1),
        "client_hours": round(client_hours, 1),
        "internal_hours": round(internal_hours, 1),
        "paid_hours": round(paid_hours, 1),
        "unpaid_hours": round(unpaid_hours, 1),
        "total_hours": round(planned_hours + unplanned_hours, 1),
        "capacity_utilization": capacity_utilization,
    }


def chore_compliance_report(start=None, end=None):
    query = ChoreOccurrence.query.filter(ChoreOccurrence.occurrence_date <= date.today())
    if start:
        query = query.filter(ChoreOccurrence.occurrence_date >= start)
    if end:
        query = query.filter(ChoreOccurrence.occurrence_date <= end)
    occurrences = query.all()

    on_time, late, missed = [], [], []
    for occ in occurrences:
        if occ.status == "completed" and occ.completed_at:
            if occ.completed_at.date() <= occ.occurrence_date:
                on_time.append(occ)
            else:
                late.append(occ)
        elif occ.status in ("pending", "escalated"):
            missed.append(occ)

    assessed = len(on_time) + len(late) + len(missed)
    compliance_rate = round(len(on_time) / assessed * 100, 1) if assessed else None

    by_user = Counter()
    by_user_total = Counter()
    for occ in on_time + late + missed:
        name = occ.chore.assigned_user.full_name if occ.chore and occ.chore.assigned_user else "Unassigned"
        by_user_total[name] += 1
        if occ in on_time:
            by_user[name] += 1
    worst_compliance = sorted(
        (
            {"user": name, "on_time": by_user[name], "total": total,
             "rate": round(by_user[name] / total * 100, 1)}
            for name, total in by_user_total.items()
        ),
        key=lambda row: row["rate"],
    )

    return {
        "assessed_count": assessed,
        "on_time_count": len(on_time),
        "late_count": len(late),
        "missed_count": len(missed),
        "compliance_rate": compliance_rate,
        "by_user": worst_compliance,
        "occurrences": sorted(late + missed, key=lambda o: o.occurrence_date),
    }


def interruption_report(start=None, end=None):
    query = Interruption.query
    if start:
        query = query.filter(Interruption.start_time >= start)
    if end:
        query = query.filter(Interruption.start_time <= end)
    interruptions = query.all()

    total_minutes = sum(i.duration_minutes or 0 for i in interruptions)
    context_switch_minutes = sum(i.context_switch_minutes or 0 for i in interruptions)
    avg_duration = round(total_minutes / len(interruptions), 1) if interruptions else 0

    by_source = Counter()
    by_project = Counter()
    for i in interruptions:
        if i.interrupted_by:
            by_source[i.interrupted_by.full_name] += 1
        if i.project:
            by_project[i.project.title] += 1

    return {
        "interruptions": interruptions,
        "total_count": len(interruptions),
        "total_hours": round(total_minutes / 60, 1),
        "context_switch_hours": round(context_switch_minutes / 60, 1),
        "avg_duration_minutes": avg_duration,
        "by_source": by_source.most_common(10),
        "most_interrupted_projects": by_project.most_common(10),
    }


def executive_summary():
    critical_projects = (
        Project.query.join(Project.priority_level).filter_by(name="Critical").filter(Project.is_archived.is_(False)).all()
    )
    at_risk = Project.query.filter_by(health_status="at_risk", is_archived=False).all()
    off_track = Project.query.filter_by(health_status="off_track", is_archived=False).all()
    blocked = Project.query.filter(Project.roadblocks.isnot(None), Project.roadblocks != "", Project.is_archived.is_(False)).all()

    week_ago = date.today() - timedelta(days=7)
    recent_overrides = (
        PriorityEvent.query.filter(PriorityEvent.occurred_at >= week_ago)
        .order_by(PriorityEvent.occurred_at.desc()).limit(10).all()
    )

    total_unplanned_hours = sum(
        (t.hours for t in TimeEntry.query.filter(TimeEntry.category == "unplanned", TimeEntry.entry_date >= week_ago).all())
    )

    return {
        "critical_projects": critical_projects,
        "at_risk": at_risk,
        "off_track": off_track,
        "blocked": blocked,
        "recent_overrides": recent_overrides,
        "unplanned_hours_this_week": round(total_unplanned_hours, 1),
    }

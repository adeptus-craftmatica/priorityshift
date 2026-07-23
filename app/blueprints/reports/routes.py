from datetime import datetime

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.services.exports import export_response
from app.services.forecast_service import get_org_forecast
from app.services.permissions import requires_permission
from app.services.reports_service import (
    chore_compliance_report, deadline_impact_report, executive_summary,
    interruption_report, priority_change_report, workload_report,
)

bp = Blueprint("reports", __name__)


def _date_range():
    start = request.args.get("start")
    end = request.args.get("end")
    start_dt = datetime.strptime(start, "%Y-%m-%d") if start else None
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else None
    return start_dt, end_dt


def _export_format():
    fmt = request.args.get("export")
    return fmt if fmt in ("csv", "xlsx", "pdf") else None


@bp.route("/")
@login_required
def index():
    return render_template("reports/index.html")


@bp.route("/priority-changes")
@login_required
def priority_changes():
    start, end = _date_range()
    data = priority_change_report(start, end)
    fmt = _export_format()
    if fmt:
        rows = [
            [e.occurred_at, e.item_type, e.item_id,
             e.previous_priority_level.name if e.previous_priority_level else "",
             e.new_priority_level.name if e.new_priority_level else "",
             e.requested_by.full_name if e.requested_by else "", e.reason]
            for e in data["events"]
        ]
        return export_response(
            fmt, "priority_changes", ["Date", "Type", "Item ID", "From", "To", "Requested By", "Reason"], rows,
            title="Priority Change Report",
        )
    return render_template("reports/priority_changes.html", data=data)


@bp.route("/deadline-impact")
@login_required
def deadline_impact():
    start, end = _date_range()
    data = deadline_impact_report(start, end)
    fmt = _export_format()
    if fmt:
        rows = [
            [r.changed_at, r.project.project_number if r.project else "", r.previous_deadline, r.new_deadline, r.estimated_hours_lost, r.reason]
            for r in data["revisions"]
        ]
        return export_response(
            fmt, "deadline_impact", ["Date", "Project", "Previous Deadline", "New Deadline", "Hours Lost", "Reason"], rows,
            title="Deadline Impact Report",
        )
    return render_template("reports/deadline_impact.html", data=data)


@bp.route("/workload")
@login_required
@requires_permission("export_reports")
def workload():
    start, end = _date_range()
    data = workload_report(start, end)
    fmt = _export_format()
    if fmt:
        rows = [[name, hours] for name, hours in data["by_developer"]]
        return export_response(fmt, "workload", ["Developer", "Hours"], rows, title="Workload Report")
    return render_template("reports/workload.html", data=data)


@bp.route("/interruptions")
@login_required
def interruptions():
    start, end = _date_range()
    data = interruption_report(start, end)
    fmt = _export_format()
    if fmt:
        rows = [
            [i.start_time, i.user.full_name if i.user else "", i.project.project_number if i.project else "",
             i.duration_minutes, i.reason]
            for i in data["interruptions"]
        ]
        return export_response(fmt, "interruptions", ["Date", "User", "Project", "Minutes", "Reason"], rows, title="Interruption Report")
    return render_template("reports/interruptions.html", data=data)


@bp.route("/chore-compliance")
@login_required
@requires_permission("export_reports")
def chore_compliance():
    start, end = _date_range()
    data = chore_compliance_report(start, end)
    fmt = _export_format()
    if fmt:
        rows = [
            [o.occurrence_date, o.chore.chore_number if o.chore else "",
             o.chore.assigned_user.full_name if o.chore and o.chore.assigned_user else "", o.status]
            for o in data["occurrences"]
        ]
        return export_response(
            fmt, "chore_compliance", ["Due Date", "Chore", "Assignee", "Status"], rows,
            title="Chore Compliance Report",
        )
    return render_template("reports/chore_compliance.html", data=data)


@bp.route("/workload-forecast")
@login_required
@requires_permission("export_reports")
def workload_forecast():
    weeks_ahead = request.args.get("weeks", 8, type=int)
    data = get_org_forecast(weeks_ahead=weeks_ahead)
    fmt = _export_format()
    if fmt:
        rows = [
            [f["user"].full_name, f["effective_capacity_per_week"], f["weeks_of_backlog"], f["overloaded_week_count"]]
            for f in data["developer_forecasts"]
        ]
        return export_response(
            fmt, "workload_forecast",
            ["Developer", "Effective Capacity/wk", "Weeks of Backlog", "Overloaded Weeks"], rows,
            title="Workload Forecast Report",
        )
    return render_template("reports/workload_forecast.html", data=data, weeks_ahead=weeks_ahead)


@bp.route("/executive-summary")
@login_required
@requires_permission("view_org_dashboard")
def executive():
    data = executive_summary()
    return render_template("reports/executive_summary.html", data=data)

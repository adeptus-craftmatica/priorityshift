from datetime import date

from flask import Blueprint, render_template, request
from flask_login import login_required

from app.services.calendar_service import get_month_grid

bp = Blueprint("calendar", __name__)


@bp.route("/")
@login_required
def index():
    today = date.today()
    year = request.args.get("year", today.year, type=int)
    month = request.args.get("month", today.month, type=int)
    if month < 1 or month > 12:
        year, month = today.year, today.month
    data = get_month_grid(year, month)
    return render_template("calendar/index.html", data=data)

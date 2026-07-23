from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Notification
from app.services.search import global_search

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.personal"))
    return redirect(url_for("auth.login"))


@bp.route("/search")
@login_required
def search():
    query_text = request.args.get("q", "")
    results = global_search(query_text)
    if request.headers.get("HX-Request"):
        return render_template("main/_search_results.html", q=query_text, results=results)
    return render_template("main/search.html", q=query_text, results=results)


@bp.route("/notifications")
@login_required
def notifications():
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    if request.headers.get("HX-Request"):
        return render_template("main/_notifications_list.html", items=items)
    return render_template("main/notifications.html", items=items)


@bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    notification.is_read = True
    db.session.commit()
    if request.headers.get("HX-Request"):
        return "", 204
    return redirect(url_for("main.notifications"))


@bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("main.notifications"))

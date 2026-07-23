"""Real delivery for in-app notifications — email via SMTP, Slack/Teams via
incoming webhook. Off by default (NOTIFICATION_DELIVERY_ENABLED=false) so a
fresh checkout never tries to send anything; turning it on without any of
the channel settings configured is still safe, each channel just no-ops.
Delivery is always best-effort: a failure here must never break the request
that created the notification, so every exception is caught and logged."""

import json
import smtplib
import urllib.request
from email.message import EmailMessage

from flask import current_app


def _is_enabled():
    return bool(current_app.config.get("NOTIFICATION_DELIVERY_ENABLED"))


def is_email_configured():
    return bool(current_app.config.get("MAIL_SERVER"))


def is_slack_configured():
    return bool(current_app.config.get("SLACK_WEBHOOK_URL"))


def is_teams_configured():
    return bool(current_app.config.get("TEAMS_WEBHOOK_URL"))


def send_email(to_email, subject, body):
    if not is_email_configured():
        return False
    try:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
        message["To"] = to_email
        message.set_content(body or "")

        with smtplib.SMTP(current_app.config["MAIL_SERVER"], current_app.config["MAIL_PORT"], timeout=10) as smtp:
            if current_app.config.get("MAIL_USE_TLS"):
                smtp.starttls()
            if current_app.config.get("MAIL_USERNAME"):
                smtp.login(current_app.config["MAIL_USERNAME"], current_app.config["MAIL_PASSWORD"])
            smtp.send_message(message)
        return True
    except Exception:
        current_app.logger.exception("Failed to send notification email to %s", to_email)
        return False


def _post_webhook(url, payload, label):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10):
            pass
        return True
    except Exception:
        current_app.logger.exception("Failed to post %s webhook", label)
        return False


def send_slack_message(text):
    if not is_slack_configured():
        return False
    return _post_webhook(current_app.config["SLACK_WEBHOOK_URL"], {"text": text}, "Slack")


def send_teams_message(text):
    if not is_teams_configured():
        return False
    payload = {"@type": "MessageCard", "@context": "http://schema.org/extensions", "text": text}
    return _post_webhook(current_app.config["TEAMS_WEBHOOK_URL"], payload, "Teams")


def deliver_notification(notification):
    """Fire-and-forget delivery for one Notification. Safe to call whether
    or not delivery is enabled/configured — every branch is a no-op until
    explicitly turned on."""
    if not _is_enabled():
        return
    if notification is None or notification.user is None:
        return

    try:
        if is_email_configured() and notification.user.email:
            send_email(notification.user.email, notification.title, notification.body or "")
        text = f"*{notification.title}*\n{notification.body or ''}".strip()
        if is_slack_configured():
            send_slack_message(text)
        if is_teams_configured():
            send_teams_message(text)
    except Exception:
        current_app.logger.exception("Notification delivery failed for user_id=%s", notification.user_id)

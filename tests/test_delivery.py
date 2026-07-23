from unittest.mock import MagicMock, patch

from app.services import delivery


def test_delivery_noop_when_disabled(app, employee_user):
    with app.app_context():
        app.config["NOTIFICATION_DELIVERY_ENABLED"] = False
        app.config["MAIL_SERVER"] = "smtp.example.com"
        notification = MagicMock(user=employee_user, title="Hi", body="Body")
        with patch.object(delivery, "send_email") as mock_send:
            delivery.deliver_notification(notification)
            mock_send.assert_not_called()


def test_delivery_noop_when_enabled_but_unconfigured(app, employee_user):
    with app.app_context():
        app.config["NOTIFICATION_DELIVERY_ENABLED"] = True
        app.config["MAIL_SERVER"] = None
        app.config["SLACK_WEBHOOK_URL"] = None
        app.config["TEAMS_WEBHOOK_URL"] = None
        notification = MagicMock(user=employee_user, title="Hi", body="Body")
        with patch.object(delivery, "send_email") as mock_email, \
             patch.object(delivery, "send_slack_message") as mock_slack, \
             patch.object(delivery, "send_teams_message") as mock_teams:
            delivery.deliver_notification(notification)
            mock_email.assert_not_called()
            mock_slack.assert_not_called()
            mock_teams.assert_not_called()


def test_delivery_sends_email_when_configured(app, employee_user):
    with app.app_context():
        app.config["NOTIFICATION_DELIVERY_ENABLED"] = True
        app.config["MAIL_SERVER"] = "smtp.example.com"
        app.config["SLACK_WEBHOOK_URL"] = None
        app.config["TEAMS_WEBHOOK_URL"] = None
        notification = MagicMock(user=employee_user, user_id=employee_user.id, title="Hi", body="Body")
        with patch.object(delivery, "send_email") as mock_email:
            delivery.deliver_notification(notification)
            mock_email.assert_called_once_with(employee_user.email, "Hi", "Body")


def test_delivery_survives_smtp_exceptions(app):
    with app.app_context():
        app.config["MAIL_SERVER"] = "smtp.example.com"
        app.config["MAIL_PORT"] = 587
        app.config["MAIL_USE_TLS"] = True
        app.config["MAIL_USERNAME"] = None
        app.config["MAIL_DEFAULT_SENDER"] = "noreply@example.com"
        with patch("smtplib.SMTP", side_effect=OSError("connection refused")):
            result = delivery.send_email("someone@example.com", "Subject", "Body")
            assert result is False


def test_slack_webhook_posts_json(app):
    with app.app_context():
        app.config["SLACK_WEBHOOK_URL"] = "https://hooks.slack.example.com/xyz"
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value = MagicMock()
            result = delivery.send_slack_message("hello")
            assert result is True
            mock_urlopen.assert_called_once()


def test_slack_webhook_noop_when_unconfigured(app):
    with app.app_context():
        app.config["SLACK_WEBHOOK_URL"] = None
        with patch("urllib.request.urlopen") as mock_urlopen:
            result = delivery.send_slack_message("hello")
            assert result is False
            mock_urlopen.assert_not_called()


def test_notify_calls_delivery(app, db, employee_user):
    from app.services.notifications import notify
    with patch("app.services.notifications.deliver_notification") as mock_deliver:
        notify(employee_user, "assignment", "Test title", body="Test body")
        mock_deliver.assert_called_once()

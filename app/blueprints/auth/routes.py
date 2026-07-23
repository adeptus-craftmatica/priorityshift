from datetime import timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db, oauth
from app.blueprints.auth.forms import LoginForm, MfaCodeForm, MfaDisableForm
from app.models import User
from app.services.mfa_service import generate_secret, provisioning_uri, verify_code

bp = Blueprint("auth", __name__)

MFA_SESSION_KEYS = ("mfa_pending_user_id", "mfa_remember", "mfa_next", "mfa_attempts")


def _clear_mfa_session():
    for key in MFA_SESSION_KEYS:
        session.pop(key, None)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.personal"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip().lower()).first()
        if user and user.active and user.check_password(form.password.data):
            if user.mfa_enabled:
                session["mfa_pending_user_id"] = user.id
                session["mfa_remember"] = form.remember.data
                session["mfa_next"] = request.args.get("next")
                session["mfa_attempts"] = 0
                return redirect(url_for("auth.mfa_verify"))
            login_user(user, remember=form.remember.data, duration=timedelta(days=30))
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard.personal"))
        flash("That username or password isn't right.", "error")

    return render_template("auth/login.html", form=form)


@bp.route("/mfa", methods=["GET", "POST"])
def mfa_verify():
    user_id = session.get("mfa_pending_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))
    user = User.query.get(user_id)
    if not user or not user.mfa_enabled:
        _clear_mfa_session()
        return redirect(url_for("auth.login"))

    form = MfaCodeForm()
    if form.validate_on_submit():
        if verify_code(user.mfa_secret, form.code.data):
            remember = session.get("mfa_remember", False)
            next_url = session.get("mfa_next")
            _clear_mfa_session()
            login_user(user, remember=remember, duration=timedelta(days=30))
            return redirect(next_url or url_for("dashboard.personal"))

        session["mfa_attempts"] = session.get("mfa_attempts", 0) + 1
        if session["mfa_attempts"] >= 5:
            _clear_mfa_session()
            flash("Too many incorrect codes. Please sign in again.", "error")
            return redirect(url_for("auth.login"))
        flash("That code isn't right.", "error")

    return render_template("auth/mfa_verify.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@bp.route("/account")
@login_required
def account():
    return render_template(
        "auth/account.html", disable_form=MfaDisableForm(),
        setup_secret=session.get("mfa_setup_secret"),
    )


@bp.route("/account/mfa/enable", methods=["POST"])
@login_required
def mfa_enable():
    secret = generate_secret()
    session["mfa_setup_secret"] = secret
    uri = provisioning_uri(secret, current_user.email)
    return render_template(
        "auth/mfa_setup.html", secret=secret, uri=uri, form=MfaCodeForm(),
    )


@bp.route("/account/mfa/confirm", methods=["POST"])
@login_required
def mfa_confirm():
    secret = session.get("mfa_setup_secret")
    form = MfaCodeForm()
    if not secret:
        flash("Start two-factor setup again.", "error")
        return redirect(url_for("auth.account"))

    if form.validate_on_submit() and verify_code(secret, form.code.data):
        current_user.mfa_secret = secret
        current_user.mfa_enabled = True
        db.session.commit()
        session.pop("mfa_setup_secret", None)
        flash("Two-factor authentication is now enabled.", "success")
        return redirect(url_for("auth.account"))

    flash("That code isn't right — scan the code again and retry.", "error")
    uri = provisioning_uri(secret, current_user.email)
    return render_template("auth/mfa_setup.html", secret=secret, uri=uri, form=form)


@bp.route("/account/mfa/disable", methods=["POST"])
@login_required
def mfa_disable():
    form = MfaDisableForm()
    if form.validate_on_submit() and current_user.check_password(form.password.data):
        current_user.mfa_enabled = False
        current_user.mfa_secret = None
        db.session.commit()
        flash("Two-factor authentication disabled.", "success")
    else:
        flash("That password isn't right.", "error")
    return redirect(url_for("auth.account"))


@bp.route("/sso/login")
def sso_login():
    client = oauth.create_client("oidc")
    if client is None:
        abort(404)
    session["sso_next"] = request.args.get("next")
    return client.authorize_redirect(url_for("auth.sso_callback", _external=True))


@bp.route("/sso/callback")
def sso_callback():
    client = oauth.create_client("oidc")
    if client is None:
        abort(404)

    token = client.authorize_access_token()
    userinfo = token.get("userinfo") or client.userinfo(token=token)
    email = (userinfo or {}).get("email")

    if not email:
        flash("Your identity provider didn't return an email address.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if not user or not user.active:
        flash(f"No PriorityShift account found for {email}. Ask an admin to create one first.", "error")
        return redirect(url_for("auth.login"))

    login_user(user, remember=True, duration=timedelta(days=30))
    next_url = session.pop("sso_next", None)
    return redirect(next_url or url_for("dashboard.personal"))

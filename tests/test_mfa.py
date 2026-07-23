import pyotp

from app.extensions import db


def test_login_without_mfa_logs_in_directly(client, employee_user):
    resp = client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    assert resp.status_code == 302
    assert "/auth/mfa" not in resp.headers["Location"]


def test_login_with_mfa_enabled_requires_second_step(client, db, employee_user):
    secret = pyotp.random_base32()
    employee_user.mfa_enabled = True
    employee_user.mfa_secret = secret
    db.session.commit()

    resp = client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/auth/mfa")

    # Not logged in yet — dashboard should redirect to login.
    dashboard_resp = client.get("/dashboard/")
    assert dashboard_resp.status_code == 302


def test_mfa_verify_with_correct_code_completes_login(client, db, employee_user):
    secret = pyotp.random_base32()
    employee_user.mfa_enabled = True
    employee_user.mfa_secret = secret
    db.session.commit()

    client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    code = pyotp.TOTP(secret).now()
    resp = client.post("/auth/mfa", data={"code": code})
    assert resp.status_code == 302

    dashboard_resp = client.get("/dashboard/")
    assert dashboard_resp.status_code == 200


def test_mfa_verify_with_wrong_code_does_not_log_in(client, db, employee_user):
    secret = pyotp.random_base32()
    employee_user.mfa_enabled = True
    employee_user.mfa_secret = secret
    db.session.commit()

    client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    resp = client.post("/auth/mfa", data={"code": "000000"})
    assert resp.status_code == 200

    dashboard_resp = client.get("/dashboard/")
    assert dashboard_resp.status_code == 302


def test_mfa_verify_locks_out_after_five_failed_attempts(client, db, employee_user):
    secret = pyotp.random_base32()
    employee_user.mfa_enabled = True
    employee_user.mfa_secret = secret
    db.session.commit()

    client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    for _ in range(5):
        resp = client.post("/auth/mfa", data={"code": "000000"})

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/auth/login")


def test_enroll_and_confirm_mfa_via_account_page(client, db, employee_user):
    login_resp = client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    assert login_resp.status_code == 302

    enable_resp = client.post("/auth/account/mfa/enable")
    assert enable_resp.status_code == 200
    assert b"Confirm with a code" in enable_resp.data

    with client.session_transaction() as sess:
        secret = sess["mfa_setup_secret"]

    code = pyotp.TOTP(secret).now()
    confirm_resp = client.post("/auth/account/mfa/confirm", data={"code": code}, follow_redirects=True)
    assert confirm_resp.status_code == 200

    db.session.refresh(employee_user)
    assert employee_user.mfa_enabled is True
    assert employee_user.mfa_secret == secret


def test_disable_mfa_requires_correct_password(client, db, employee_user):
    secret = pyotp.random_base32()
    employee_user.mfa_enabled = True
    employee_user.mfa_secret = secret
    db.session.commit()

    client.post("/auth/login", data={"username": "employee1", "password": "testpass123"})
    client.post("/auth/mfa", data={"code": pyotp.TOTP(secret).now()})

    client.post("/auth/account/mfa/disable", data={"password": "wrong-password"})
    db.session.refresh(employee_user)
    assert employee_user.mfa_enabled is True

    client.post("/auth/account/mfa/disable", data={"password": "testpass123"})
    db.session.refresh(employee_user)
    assert employee_user.mfa_enabled is False

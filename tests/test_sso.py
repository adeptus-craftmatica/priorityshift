def test_sso_button_hidden_when_unconfigured(client):
    resp = client.get("/auth/login")
    assert b"Sign in with" not in resp.data


def test_sso_login_route_404s_when_unconfigured(client):
    resp = client.get("/auth/sso/login")
    assert resp.status_code == 404


def test_sso_callback_route_404s_when_unconfigured(client):
    resp = client.get("/auth/sso/callback")
    assert resp.status_code == 404


def test_sso_button_shown_when_configured(client, app):
    app.config["OIDC_CLIENT_ID"] = "test-client"
    app.config["OIDC_DISCOVERY_URL"] = "https://example.com/.well-known/openid-configuration"
    app.config["OIDC_PROVIDER_NAME"] = "Acme SSO"
    resp = client.get("/auth/login")
    assert b"Sign in with Acme SSO" in resp.data

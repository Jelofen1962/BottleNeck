from __future__ import annotations


def register(client, email: str = "owner@example.test"):
    return client.post(
        "/api/auth/register",
        json={
            "name": "BottleNeck Test Owner",
            "email": email,
            "password": "a-long-test-password-2026",
            "workspace_name": "Test Workspace",
        },
    )


def test_health_and_security_headers(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["application"] == "BottleNeck"
    assert response.json()["version"] == "1.0.0"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "SAMEORIGIN"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_register_then_login(client):
    created = register(client)
    assert created.status_code == 200, created.text
    assert "bottleneck_session" in created.cookies
    assert created.headers.get("set-cookie", "").lower().find("httponly") >= 0

    client.post("/api/auth/logout")
    logged_in = client.post(
        "/api/auth/login",
        json={"email": "owner@example.test", "password": "a-long-test-password-2026", "remember_me": True},
    )
    assert logged_in.status_code == 200, logged_in.text
    set_cookie = logged_in.headers.get("set-cookie", "").lower()
    assert "max-age=2592000" in set_cookie
    assert "httponly" in set_cookie


def test_cross_origin_state_change_is_rejected(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.test", "password": "incorrect"},
        headers={"Origin": "https://attacker.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403


def test_login_rate_limit_returns_retry_after(client):
    # The account does not need to exist to exercise the credential endpoint limiter.
    response = None
    for _ in range(11):
        response = client.post(
            "/api/auth/login",
            json={"email": "missing@example.test", "password": "wrong-password"},
        )
    assert response is not None
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_health_does_not_require_auth(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/bootstrap").status_code in {200, 401}


def test_same_origin_state_change_is_allowed(client):
    response = register(client, email="same-origin@example.test")
    assert response.status_code == 200, response.text


def test_production_mode_disables_api_docs():
    import os
    import subprocess
    import sys

    env = os.environ.copy()
    env["BOTTLENECK_ENV"] = "production"
    env.pop("BOTTLENECK_ENABLE_API_DOCS", None)
    result = subprocess.run(
        [sys.executable, "-c", "import main; assert main.app.docs_url is None; assert main.app.openapi_url is None"],
        cwd=__import__("pathlib").Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

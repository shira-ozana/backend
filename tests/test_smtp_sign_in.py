"""Sign-in code delivery over SMTP, verified against a mocked transport (no network)."""

import logging
import re
import smtplib
import socket
import ssl

import pytest
from fastapi.testclient import TestClient

from app import auth, mailer
from app.config import get_settings

APP_PASSWORD = "abcd efgh ijkl mnop"  # Google shows App Passwords in groups of four
SENDER = "sender@gmail.com"
USER_ROW = {
    "user_id": "u-1",
    "first_name": "Test",
    "last_name": "User",
    "email": "stored.address@gmail.com",
    "username": "tester",
    "created_at": "2026-01-01T00:00:00+00:00",
}


PUBLIC_FIELDS = {"challenge", "expires_in", "delivery"}


class FakeSMTP:
    """Records every call in order. Failures are injected through class attributes."""

    instances = []
    fail_on = {}  # method name -> exception to raise

    def __init__(self, host, port=0, timeout=None, **kwargs):
        self.host, self.port, self.timeout = host, port, timeout
        self.calls = []
        self.sent = []
        FakeSMTP.instances.append(self)
        self._maybe_fail("connect")

    def _maybe_fail(self, name):
        if name in FakeSMTP.fail_on:
            raise FakeSMTP.fail_on[name]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, *args, **kwargs):
        self.calls.append("starttls")
        self.starttls_context = kwargs.get("context")
        self._maybe_fail("starttls")

    def login(self, user, password):
        self.calls.append("login")
        self.login_args = (user, password)
        self._maybe_fail("login")

    def send_message(self, message):
        self.calls.append("send_message")
        self._maybe_fail("send_message")
        self.sent.append(message)


@pytest.fixture(autouse=True)
def smtp_env(monkeypatch):
    for key, value in {
        "AUTH_EMAIL_MODE": "smtp",
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "587",
        "SMTP_STARTTLS": "true",
        "SMTP_USER": SENDER,
        "SMTP_PASSWORD": APP_PASSWORD,
        "SMTP_FROM": SENDER,
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    FakeSMTP.instances = []
    FakeSMTP.fail_on = {}
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    auth.limits = auth._Limits()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(monkeypatch):
    from app.main import app
    from app.routers import auth as auth_router

    def find_user(identifier):
        if identifier.strip().lower() in ("tester", USER_ROW["email"]):
            return dict(USER_ROW)
        return None

    def by_id(user_id):
        return dict(USER_ROW) if user_id == USER_ROW["user_id"] else None

    monkeypatch.setattr(auth_router, "find_user", find_user)
    monkeypatch.setattr(auth_router, "get_user_by_id", by_id)
    monkeypatch.setattr(auth, "get_user_by_id", by_id)
    return TestClient(app)


def _code_from(smtp):
    body = smtp.sent[0].get_content()
    return re.search(r"\b(\d{6})\b", body).group(1)


def test_sends_code_to_stored_address_with_starttls_before_login(client):
    response = client.post("/api/auth/sign-in/request", json={"identifier": "tester"})

    assert response.status_code == 202
    (smtp,) = FakeSMTP.instances
    assert (smtp.host, smtp.port) == ("smtp.gmail.com", 587)
    assert smtp.calls == ["starttls", "login", "send_message"]
    assert smtp.timeout is not None and 0 < smtp.timeout <= 30
    # Certificate and hostname verification are on.
    assert isinstance(smtp.starttls_context, ssl.SSLContext)
    assert smtp.starttls_context.verify_mode == ssl.CERT_REQUIRED
    assert smtp.starttls_context.check_hostname is True
    # The App Password is passed without the display spaces.
    assert smtp.login_args == (SENDER, APP_PASSWORD.replace(" ", ""))
    message = smtp.sent[0]
    assert message["To"] == USER_ROW["email"]
    assert message["From"] == SENDER


def test_request_by_email_uses_the_stored_address(client):
    response = client.post("/api/auth/sign-in/request", json={"identifier": USER_ROW["email"]})
    assert response.status_code == 202
    assert FakeSMTP.instances[0].sent[0]["To"] == USER_ROW["email"]


def test_unknown_account_gets_same_response_and_no_email(client):
    known = client.post("/api/auth/sign-in/request", json={"identifier": "tester"})
    unknown = client.post("/api/auth/sign-in/request", json={"identifier": "nobody"})

    assert unknown.status_code == known.status_code == 202
    assert set(unknown.json()) == set(known.json()) == PUBLIC_FIELDS
    assert unknown.json()["expires_in"] == known.json()["expires_in"]
    assert len(FakeSMTP.instances) == 1  # only the known account caused a connection


def test_request_response_never_contains_the_code(client):
    response = client.post("/api/auth/sign-in/request", json={"identifier": "tester"})
    code = _code_from(FakeSMTP.instances[0])
    assert code not in response.text
    assert "code" not in response.json()


def test_delivered_code_signs_in_and_sets_session(client):
    challenge = client.post("/api/auth/sign-in/request", json={"identifier": "tester"}).json()[
        "challenge"
    ]
    code = _code_from(FakeSMTP.instances[0])

    assert client.get("/api/auth/me").status_code == 401
    verify = client.post("/api/auth/sign-in/verify", json={"challenge": challenge, "code": code})

    assert verify.status_code == 200
    assert auth.SESSION_COOKIE in verify.cookies
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user_id"] == USER_ROW["user_id"]
    assert me.json()["email"] == USER_ROW["email"]


@pytest.mark.parametrize(
    "env",
    [
        {"SMTP_HOST": ""},  # no host
        {"SMTP_PASSWORD": ""},  # user without password
        {"SMTP_STARTTLS": "false"},  # would send the login in clear text
        {"AUTH_EMAIL_MODE": "disabled"},
    ],
)
def test_missing_configuration_returns_503_and_sends_nothing(client, monkeypatch, env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()

    response = client.post("/api/auth/sign-in/request", json={"identifier": "tester"})

    assert response.status_code == 503
    assert FakeSMTP.instances == []
    assert APP_PASSWORD not in response.text


def test_unconfigured_is_503_for_unknown_accounts_too(client, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()
    assert client.post("/api/auth/sign-in/request", json={"identifier": "nobody"}).status_code == 503


@pytest.mark.parametrize(
    "step, error, category",
    [
        ("login", smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted"), "authentication"),
        ("starttls", ssl.SSLCertVerificationError("certificate verify failed"), "tls"),
        ("starttls", smtplib.SMTPNotSupportedError("STARTTLS extension not supported"), "tls"),
        ("connect", socket.timeout("timed out"), "timeout"),
        ("connect", ConnectionRefusedError("refused"), "connection"),
        ("send_message", smtplib.SMTPRecipientsRefused({USER_ROW["email"]: (550, b"no such user")}), "recipient_rejected"),
    ],
)
def test_smtp_failures_are_logged_by_category_without_leaking(
    client, caplog, step, error, category
):
    FakeSMTP.fail_on = {step: error}
    with caplog.at_level(logging.ERROR, logger="uvicorn.error"):
        response = client.post("/api/auth/sign-in/request", json={"identifier": "tester"})

    # The public answer does not change when delivery fails.
    assert response.status_code == 202
    assert set(response.json()) == PUBLIC_FIELDS

    assert f"category={category}" in caplog.text
    log = caplog.text
    assert APP_PASSWORD not in log and APP_PASSWORD.replace(" ", "") not in log
    assert USER_ROW["email"] not in log
    assert "sign-in code is" not in log
    assert not re.search(r"\b\d{6}\b", log)
    for record in caplog.records:
        assert record.exc_info is None  # no traceback with server replies or addresses


def test_authentication_is_never_attempted_after_a_tls_failure(client):
    FakeSMTP.fail_on = {"starttls": ssl.SSLError("handshake failed")}
    client.post("/api/auth/sign-in/request", json={"identifier": "tester"})
    assert FakeSMTP.instances[0].calls == ["starttls"]


def test_console_mode_still_works_without_smtp(client, monkeypatch, caplog):
    monkeypatch.setenv("AUTH_EMAIL_MODE", "console")
    monkeypatch.setenv("SMTP_HOST", "")
    get_settings.cache_clear()

    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = client.post("/api/auth/sign-in/request", json={"identifier": "tester"})

    assert response.status_code == 202
    assert FakeSMTP.instances == []
    code = re.search(r"DEV sign-in code for \S+: (\d{6})", caplog.text).group(1)
    assert code not in response.text

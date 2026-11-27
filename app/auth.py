"""Cookie sessions and email one-time-code sign-in.

Design (no new database tables, so no schema migration is needed):

* A session is a signed, HttpOnly cookie holding ``{sub: user_id, exp}``. It is issued only by
  ``POST /api/users`` (the request that created the account) and by a successful
  ``POST /api/auth/sign-in/verify``.
* Signing in to an *existing* account needs proof of ownership: a 6-digit code sent to the
  email address stored on that account. A username, an email typed into a form, or a ``409``
  on registration never produce a session.
* The challenge returned by ``sign-in/request`` is a signed token holding an HMAC of the code,
  keyed with a server secret, so the code cannot be recovered or guessed offline.
* Challenge single-use, attempt limits and request rate limits are kept in process memory.
  That is enough for a single uvicorn process; with several workers use a shared store.
"""

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, Response

from app.config import get_settings
from app.lookups import get_user_by_id

SESSION_COOKIE = "shipai_session"

CHALLENGE_TTL_SECONDS = 10 * 60
MAX_CODE_ATTEMPTS = 5
MAX_REQUESTS_PER_WINDOW = 5
REQUEST_WINDOW_SECONDS = 15 * 60


# ---------------------------------------------------------------------------
# Signed tokens
# ---------------------------------------------------------------------------


def _secret() -> bytes:
    settings = get_settings()
    if settings.session_secret:
        return settings.session_secret.encode()
    # Derived from the existing encryption key so no extra setting is required.
    return hmac.new(settings.encryption_key.encode(), b"shipai-session-v1", hashlib.sha256).digest()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: Dict[str, Any]) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def _unsign(token: str, typ: str) -> Optional[Dict[str, Any]]:
    """Returns the payload when the signature, type and expiry are valid, else None."""
    try:
        body, sig = token.split(".", 1)
        expected = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
    except Exception:  # noqa: BLE001 - any malformed token is simply invalid
        return None
    if not isinstance(payload, dict) or payload.get("typ") != typ:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)) or exp < time.time():
        return None
    return payload


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def start_session(response: Response, user_id: str) -> None:
    settings = get_settings()
    ttl = settings.session_ttl_hours * 3600
    token = _sign({"typ": "session", "sub": user_id, "exp": int(time.time()) + ttl})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=ttl,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


def end_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def require_session(request: Request) -> Dict[str, Any]:
    """FastAPI dependency: the current user row, or 401 when there is no valid session."""
    token = request.cookies.get(SESSION_COOKIE)
    payload = _unsign(token, "session") if token else None
    user = get_user_by_id(str(payload["sub"])) if payload else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return user


# ---------------------------------------------------------------------------
# Email one-time code
# ---------------------------------------------------------------------------


def _code_digest(nonce: str, code: str) -> str:
    return hmac.new(_secret(), f"code:{nonce}:{code}".encode(), hashlib.sha256).hexdigest()


class _Limits:
    """Process-local counters. Entries expire with the thing they protect."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Dict[str, list] = {}
        self._attempts: Dict[str, int] = {}
        self._used: Dict[str, float] = {}

    def allow_request(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            recent = [t for t in self._requests.get(key, []) if now - t < REQUEST_WINDOW_SECONDS]
            if len(recent) >= MAX_REQUESTS_PER_WINDOW:
                self._requests[key] = recent
                return False
            recent.append(now)
            self._requests[key] = recent
            return True

    def is_spent(self, nonce: str) -> bool:
        with self._lock:
            return nonce in self._used or self._attempts.get(nonce, 0) >= MAX_CODE_ATTEMPTS

    def record_failure(self, nonce: str) -> None:
        with self._lock:
            self._attempts[nonce] = self._attempts.get(nonce, 0) + 1

    def mark_used(self, nonce: str, exp: float) -> None:
        now = time.time()
        with self._lock:
            self._used = {n: e for n, e in self._used.items() if e > now}
            self._used[nonce] = exp


limits = _Limits()


def create_challenge(user_id: Optional[str]) -> "tuple[str, Optional[str]]":
    """Returns ``(challenge_token, code)``. ``code`` is None when there is no account.

    For an unknown identifier a challenge is still produced (with a code nobody receives) so
    the response does not reveal whether the account exists.
    """
    nonce = secrets.token_urlsafe(16)
    code = f"{secrets.randbelow(1_000_000):06d}"
    token = _sign(
        {
            "typ": "signin",
            "n": nonce,
            "u": user_id,
            "h": _code_digest(nonce, code),
            "exp": int(time.time()) + CHALLENGE_TTL_SECONDS,
        }
    )
    return token, (code if user_id else None)


def verify_challenge(challenge: str, code: str) -> str:
    """Returns the user_id the code proves ownership of, or raises 401."""
    invalid = HTTPException(status_code=401, detail="That code is invalid or has expired.")
    payload = _unsign(challenge, "signin")
    if payload is None:
        raise invalid
    nonce = str(payload.get("n"))
    if limits.is_spent(nonce):
        raise invalid

    expected = str(payload.get("h"))
    if not hmac.compare_digest(_code_digest(nonce, code.strip()), expected) or not payload.get("u"):
        limits.record_failure(nonce)
        raise invalid

    limits.mark_used(nonce, float(payload["exp"]))
    return str(payload["u"])

import logging
import smtplib
import socket
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Optional

from fastapi import HTTPException

from app.config import get_settings

# `uvicorn.error` is always shown by uvicorn, so the development code is visible in its console.
logger = logging.getLogger("uvicorn.error")

# Upper bound for connecting to and talking with the SMTP server (seconds).
SMTP_TIMEOUT_SECONDS = 15


def _smtp_configured() -> bool:
    settings = get_settings()
    if not (settings.smtp_host and settings.smtp_host.strip()):
        return False
    if settings.smtp_user and not settings.smtp_password:
        return False  # a username without its password can never authenticate
    if settings.smtp_user and not settings.smtp_starttls:
        return False  # credentials are never sent without TLS
    return True


def ensure_delivery_configured() -> None:
    """503 when sign-in codes cannot be delivered anywhere (never silently skip delivery)."""
    mode = get_settings().auth_email_mode
    if mode == "console" or (mode == "smtp" and _smtp_configured()):
        return
    raise HTTPException(
        status_code=503,
        detail=(
            "Sign-in by email code is not configured on the server. "
            "Set AUTH_EMAIL_MODE=smtp (with SMTP_HOST, and SMTP_USER + SMTP_PASSWORD when the "
            "server needs a login) or AUTH_EMAIL_MODE=console for development."
        ),
    )


def _failure_category(exc: Exception) -> str:
    """Maps an SMTP/network error to a short, safe label (no addresses, secrets or bodies)."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "authentication"
    if isinstance(exc, ssl.SSLError):  # includes certificate verification failures
        return "tls"
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "recipient_rejected"
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return "sender_rejected"
    if isinstance(exc, smtplib.SMTPNotSupportedError):
        return "tls"  # e.g. the server does not offer STARTTLS
    if isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected)):
        return "connection"
    if isinstance(exc, smtplib.SMTPException):  # must precede OSError: it is a subclass
        return "smtp"
    if isinstance(exc, OSError):
        return "connection"
    return "unexpected"


def _log_failure(exc: Exception, category: Optional[str] = None) -> None:
    # Deliberately no traceback or message text: those can carry the recipient address or
    # server replies. Only the category, the exception type and (for SMTP) the reply code.
    code = getattr(exc, "smtp_code", None)
    logger.error(
        "Sign-in code email was not delivered: category=%s error=%s%s",
        category or _failure_category(exc),
        type(exc).__name__,
        f" smtp_code={code}" if isinstance(code, int) else "",
    )


def send_sign_in_code(to_email: str, code: str) -> None:
    settings = get_settings()
    if settings.auth_email_mode == "console":
        # Development only: the code goes to the server log, never to the HTTP response.
        logger.warning("DEV sign-in code for %s: %s", to_email, code)
        return

    sender = settings.smtp_from or settings.smtp_user or "no-reply@localhost"
    message = EmailMessage()
    message["Subject"] = f"Your {settings.app_name} sign-in code"
    message["From"] = sender
    message["To"] = to_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1] or None)
    message.set_content(
        f"Your {settings.app_name} sign-in code is {code}.\n"
        "It expires in 10 minutes. If you did not ask for it, ignore this email."
    )

    # Never send a login over an unencrypted connection.
    if settings.smtp_user and not settings.smtp_starttls:
        logger.error(
            "Sign-in code email was not delivered: category=configuration "
            "error=SMTP_USER is set but SMTP_STARTTLS is false; refusing to authenticate "
            "without TLS"
        )
        return

    try:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
        ) as smtp:
            if settings.smtp_starttls:
                # Verifies the server certificate and hostname; happens before smtp.login().
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user:
                # Google shows App Passwords in groups separated by spaces; they are not part
                # of the password.
                password = (settings.smtp_password or "").replace(" ", "")
                smtp.login(settings.smtp_user, password)
            smtp.send_message(message)
    except Exception as exc:  # noqa: BLE001 - delivery runs in the background; never raise
        _log_failure(exc)

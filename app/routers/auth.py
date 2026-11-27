from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status

from app import auth
from app.lookups import find_user, get_user_by_id
from app.mailer import ensure_delivery_configured, send_sign_in_code
from app.schemas import SignInChallenge, SignInRequest, SignInVerify, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(row: Dict[str, Any]) -> UserOut:
    return UserOut(
        user_id=row["user_id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        username=row["username"],
        created_at=row["created_at"],
    )


@router.get("/me", response_model=UserOut)
def me(user: Dict[str, Any] = Depends(auth.require_session)) -> UserOut:
    """The user the session cookie belongs to, or 401."""
    return _user_out(user)


@router.post(
    "/sign-in/request", response_model=SignInChallenge, status_code=status.HTTP_202_ACCEPTED
)
def request_sign_in(
    payload: SignInRequest, background: BackgroundTasks
) -> SignInChallenge:
    """Emails a one-time code to the address on the account.

    The answer is identical whether or not the account exists, so it cannot be used to list
    users. The code is only ever delivered to the account's own email address.
    """
    ensure_delivery_configured()
    identifier = payload.identifier.strip()
    if not auth.limits.allow_request(identifier.lower()):
        raise HTTPException(status_code=429, detail="Too many sign-in requests. Try again later.")

    user = find_user(identifier)
    challenge, code = auth.create_challenge(user["user_id"] if user else None)
    if user and code:
        background.add_task(send_sign_in_code, user["email"], code)
    return SignInChallenge(challenge=challenge, expires_in=auth.CHALLENGE_TTL_SECONDS)


@router.post("/sign-in/verify", response_model=UserOut)
def verify_sign_in(payload: SignInVerify, response: Response) -> UserOut:
    """Exchanges the emailed code for a session cookie."""
    user_id = auth.verify_challenge(payload.challenge, payload.code)
    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="That code is invalid or has expired.")
    auth.start_session(response, user["user_id"])
    return _user_out(user)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
def sign_out() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    auth.end_session(response)
    return response

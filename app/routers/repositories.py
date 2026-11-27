from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_session
from app.config import get_settings
from app.db import get_supabase
from app.schemas import RepositoryCreate, RepositoryOut
from app.security import encrypt

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
def create_repository(
    payload: RepositoryCreate, user: Dict[str, Any] = Depends(require_session)
) -> RepositoryOut:
    """Requires a session. `username` stays in the body (existing contract) but must match it."""
    if payload.username != user["username"]:
        raise HTTPException(status_code=403, detail="username does not match the signed-in user")
    record = {
        "user_id": user["user_id"],
        "github_user": payload.github_user,
        "github_password_encrypted": encrypt(payload.github_password),
        "repo_url": str(payload.repo_url),
    }
    try:
        result = get_supabase().table(get_settings().repositories_table).insert(record).execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    if not result.data:
        raise HTTPException(status_code=500, detail="Insert returned no data")
    row = result.data[0]
    return RepositoryOut(
        id=row["id"],
        user_id=row["user_id"],
        username=user["username"],
        github_user=row["github_user"],
        repo_url=row["repo_url"],
        created_at=row["created_at"],
    )

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.db import get_supabase
from app.lookups import get_user_id_by_username
from app.schemas import RepositoryCreate, RepositoryOut
from app.security import encrypt

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.post("", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
def create_repository(payload: RepositoryCreate) -> RepositoryOut:
    user_id = get_user_id_by_username(payload.username)
    record = {
        "user_id": user_id,
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
        username=payload.username,
        github_user=row["github_user"],
        repo_url=row["repo_url"],
        created_at=row["created_at"],
    )

import uuid

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.db import get_supabase
from app.schemas import UserCreate, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate) -> UserOut:
    record = {
        "user_id": str(uuid.uuid4()),
        "first_name": payload.first_name,
        "last_name": payload.last_name,
        "email": payload.email.lower(),  # מייל נשמר באותיות קטנות - ייחודיות בלי תלות ב-case
        "username": payload.username,
    }
    try:
        result = get_supabase().table(get_settings().users_table).insert(record).execute()
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        if "23505" in message:  # unique violation
            field = "email" if "email" in message else "username"
            raise HTTPException(status_code=409, detail=f"A user with this {field} already exists") from exc
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    row = result.data[0]
    return UserOut(
        user_id=row["user_id"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        email=row["email"],
        username=row["username"],
        created_at=row["created_at"],
    )

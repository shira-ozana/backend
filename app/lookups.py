from fastapi import HTTPException

from app.config import get_settings
from app.db import get_supabase


def get_user_id_by_username(username: str) -> str:
    """מחזיר את ה-user_id של שם משתמש, או 404 אם המשתמש לא רשום"""
    try:
        result = (
            get_supabase()
            .table(get_settings().users_table)
            .select("user_id")
            .eq("username", username)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    if not result.data:
        raise HTTPException(
            status_code=404, detail="User not found. Call POST /api/users first."
        )
    return result.data[0]["user_id"]

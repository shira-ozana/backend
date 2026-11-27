from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.config import get_settings
from app.db import get_supabase


def _select_one(column: str, value: str) -> Optional[Dict[str, Any]]:
    try:
        result = (
            get_supabase()
            .table(get_settings().users_table)
            .select("*")
            .eq(column, value)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc
    return result.data[0] if result.data else None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return _select_one("user_id", user_id)


def find_user(identifier: str) -> Optional[Dict[str, Any]]:
    """Looks a user up by email (when it contains "@") or by username. None when unknown."""
    identifier = identifier.strip()
    if "@" in identifier:
        return _select_one("email", identifier.lower())
    return _select_one("username", identifier)


def get_user_id_by_username(username: str) -> str:
    """מחזיר את ה-user_id של שם משתמש, או 404 אם המשתמש לא רשום"""
    user = _select_one("username", username)
    if user is None:
        raise HTTPException(
            status_code=404, detail="User not found. Call POST /api/users first."
        )
    return user["user_id"]

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.config import get_settings
from app.db import get_supabase
from app.lookups import get_user_id_by_username
from app.schemas import (
    FeatureCreate,
    FeatureItem,
    FeatureOut,
    FeaturesList,
    _validate_github_url,
)

router = APIRouter(prefix="/api/features", tags=["features"])


def _new_feature_id() -> str:
    """מזהה ייחודי (UUID4) - בטוח לשימוש כשם תיקייה ב-.platform/{feature_id}/"""
    return str(uuid.uuid4())


@router.post("", response_model=FeatureOut, status_code=status.HTTP_201_CREATED)
def create_feature(payload: FeatureCreate) -> FeatureOut:
    settings = get_settings()
    db = get_supabase()
    repo_url = str(payload.repo_url)

    # הפיצ'ר חייב להיות משויך לריפו שהמשתמש כבר רשם ב-/api/repositories
    user_id = get_user_id_by_username(payload.username)
    try:
        repo = (
            db.table(settings.repositories_table)
            .select("id")
            .eq("user_id", user_id)
            .eq("repo_url", repo_url)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    if not repo.data:
        raise HTTPException(
            status_code=404,
            detail="Repository not registered for this user. Call POST /api/repositories first.",
        )

    record = {
        "username": payload.username,
        "repo_url": repo_url,
        "feature_id": _new_feature_id(),
    }
    try:
        result = db.table(settings.features_table).insert(record).execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    row = result.data[0]
    return FeatureOut(
        feature_id=row["feature_id"],
        username=row["username"],
        repo_url=row["repo_url"],
        created_at=row["created_at"],
    )


@router.get("", response_model=FeaturesList)
def list_features(
    username: str = Query(..., min_length=1, description="שם המשתמש"),
    repo_url: str = Query(..., description="כתובת הריפו ב-GitHub"),
) -> FeaturesList:
    """מחזיר את כל הפיצ'רים של משתמש בריפו מסוים"""
    from pydantic import HttpUrl, TypeAdapter, ValidationError

    try:
        normalized = str(_validate_github_url(TypeAdapter(HttpUrl).validate_python(repo_url)))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="repo_url must be a valid github.com URL") from exc

    try:
        result = (
            get_supabase()
            .table(get_settings().features_table)
            .select("feature_id, created_at")
            .eq("username", username)
            .eq("repo_url", normalized)
            .order("created_at")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    return FeaturesList(
        username=username,
        repo_url=normalized,
        features=[FeatureItem(feature_id=r["feature_id"], created_at=r["created_at"]) for r in result.data],
    )

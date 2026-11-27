import uuid

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import HttpUrl, TypeAdapter, ValidationError

from app.config import get_settings
from app.db import get_supabase
from app.schemas import TaskCreate, TaskItem, TaskOut, TasksList, _validate_github_url

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> TaskOut:
    settings = get_settings()
    db = get_supabase()
    repo_url = str(payload.repo_url)

    try:
        uuid.UUID(payload.feature_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="feature_id must be a valid UUID") from exc

    # המשימה חייבת להיות שייכת לפיצ'ר קיים של אותו משתמש ואותו ריפו
    try:
        feature = (
            db.table(settings.features_table)
            .select("feature_id")
            .eq("username", payload.username)
            .eq("repo_url", repo_url)
            .eq("feature_id", payload.feature_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    if not feature.data:
        raise HTTPException(
            status_code=404,
            detail="Feature not found for this user and repo. Call POST /api/features first.",
        )

    record = {
        "username": payload.username,
        "repo_url": repo_url,
        "feature_id": payload.feature_id,
        "task_id": str(uuid.uuid4()),
    }
    try:
        result = db.table(settings.tasks_table).insert(record).execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    row = result.data[0]
    return TaskOut(
        task_id=row["task_id"],
        feature_id=row["feature_id"],
        username=row["username"],
        repo_url=row["repo_url"],
        created_at=row["created_at"],
    )


@router.get("", response_model=TasksList)
def list_tasks(
    username: str = Query(..., min_length=1, description="שם המשתמש"),
    repo_url: str = Query(..., description="כתובת הריפו ב-GitHub"),
    feature_id: str = Query(..., description="מזהה הפיצ'ר"),
) -> TasksList:
    """מחזיר את כל המשימות של פיצ'ר מסוים של משתמש בריפו"""
    try:
        normalized = str(_validate_github_url(TypeAdapter(HttpUrl).validate_python(repo_url)))
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="repo_url must be a valid github.com URL") from exc

    try:
        uuid.UUID(feature_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="feature_id must be a valid UUID") from exc

    try:
        result = (
            get_supabase()
            .table(get_settings().tasks_table)
            .select("task_id, created_at")
            .eq("username", username)
            .eq("repo_url", normalized)
            .eq("feature_id", feature_id)
            .order("created_at")
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Database error: {exc}") from exc

    return TasksList(
        username=username,
        repo_url=normalized,
        feature_id=feature_id,
        tasks=[TaskItem(task_id=r["task_id"], created_at=r["created_at"]) for r in result.data],
    )

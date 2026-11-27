from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator


def _validate_github_url(v: HttpUrl) -> HttpUrl:
    if v.host not in ("github.com", "www.github.com"):
        raise ValueError("repo_url must be a github.com URL")
    return v


class RepositoryCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100, description="שם המשתמש שנרשם ב-/api/users")
    github_user: str = Field(..., min_length=1, max_length=100, description="שם המשתמש ב-GitHub")
    github_password: str = Field(
        ..., min_length=1, description="סיסמה / Personal Access Token של GitHub"
    )
    repo_url: HttpUrl = Field(..., description="כתובת הריפו ב-GitHub")

    @field_validator("repo_url")
    @classmethod
    def must_be_github(cls, v: HttpUrl) -> HttpUrl:
        return _validate_github_url(v)


class RepositoryOut(BaseModel):
    """מה שחוזר לקליינט - בלי הסיסמה"""

    id: int
    user_id: str
    username: str
    github_user: str
    repo_url: str
    created_at: datetime


class FeatureCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100, description="שם המשתמש שנרשם ב-/api/users")
    repo_url: HttpUrl = Field(..., description="כתובת הריפו ב-GitHub (שנרשם קודם)")

    @field_validator("repo_url")
    @classmethod
    def must_be_github(cls, v: HttpUrl) -> HttpUrl:
        return _validate_github_url(v)


class FeatureOut(BaseModel):
    feature_id: str = Field(..., description="מזהה ייחודי - משמש לתיקייה .platform/{feature_id}/")
    username: str
    repo_url: str
    created_at: datetime


class FeatureItem(BaseModel):
    feature_id: str
    created_at: datetime


class FeaturesList(BaseModel):
    username: str
    repo_url: str
    features: list[FeatureItem] = Field(..., description="ממוין לפי זמן יצירה (מהישן לחדש)")


class TaskCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100, description="שם המשתמש שנרשם ב-/api/users")
    repo_url: HttpUrl = Field(..., description="כתובת הריפו ב-GitHub")
    feature_id: str = Field(..., description="מזהה הפיצ'ר שאליו שייכת המשימה")

    @field_validator("repo_url")
    @classmethod
    def must_be_github(cls, v: HttpUrl) -> HttpUrl:
        return _validate_github_url(v)


class TaskOut(BaseModel):
    task_id: str
    feature_id: str
    username: str
    repo_url: str
    created_at: datetime


class UserCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100, description="שם פרטי")
    last_name: str = Field(..., min_length=1, max_length=100, description="שם משפחה")
    email: EmailStr = Field(..., description="מייל - ייחודי, לשליחת מיילים")
    username: str = Field(..., min_length=1, max_length=100, description="שם משתמש - ייחודי")


class UserOut(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    email: str
    username: str
    created_at: datetime


class TaskItem(BaseModel):
    task_id: str
    created_at: datetime


class TasksList(BaseModel):
    username: str
    repo_url: str
    feature_id: str
    tasks: list[TaskItem] = Field(..., description="ממוין לפי זמן יצירה (מהישן לחדש)")

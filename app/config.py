from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """הגדרות המערכת - נטענות מקובץ .env"""

    app_name: str = "SDLC Platform"
    supabase_url: str
    supabase_service_role_key: str
    encryption_key: str
    users_table: str = "users"
    repositories_table: str = "repositories"
    features_table: str = "features"
    tasks_table: str = "tasks"

    # Sessions. Empty SESSION_SECRET derives a key from ENCRYPTION_KEY.
    session_secret: Optional[str] = None
    session_ttl_hours: int = 24 * 7
    # Set true when the API is served over HTTPS.
    session_cookie_secure: bool = False

    # How sign-in codes reach the user: "smtp", "console" (development: written to the server
    # log) or "disabled" (sign-in for existing accounts returns 503).
    auth_email_mode: str = "disabled"
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    smtp_starttls: bool = True

    # שרתי הסוכנים (Agents)
    init_agent_url: str = "http://127.0.0.1:3000"
    agent_request_timeout: float = 30.0  # שניות - לבקשות רגילות (הפעלה / סטטוס)
    agent_wait_timeout: float = 1800.0  # שניות - כשמחכים לסיום ריצה (?wait=true)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

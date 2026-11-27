from functools import lru_cache

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Central configuration, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Persistence ---
    database_url: str = "postgresql://user:password@localhost:5432/postgres"
    db_schema: str = "order_supervisor"

    # --- Temporal ---
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "order-supervisor"

    # --- LLM ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # --- Lifecycle guard rails ---
    max_workflow_age_hours: int = 168
    default_wake_interval_minutes: int = 60

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    frontend_origin: str = "http://localhost:3000"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

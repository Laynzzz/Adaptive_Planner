"""Isolated process configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLANNER_", env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://planner:local-planner-only@127.0.0.1:25432/planner"
    oidc_issuer: str = "http://127.0.0.1:28080/realms/adaptive-planner"
    oidc_client_id: str = "planner-web"

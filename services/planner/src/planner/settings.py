"""Isolated process configuration; HTTP cookies are a local-development exception."""

from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PLANNER_", env_file=".env", extra="ignore")
    database_url: str = Field(
        default="postgresql+psycopg://planner:local-planner-only@127.0.0.1:25432/planner",
        repr=False,
    )
    database_host: str | None = None
    database_username: str = "planner_app"
    database_password: SecretStr | None = None
    database_name: str = "planner"
    database_sslmode: str = "require"
    static_dist_path: Path | None = None
    oidc_issuer: str = "http://127.0.0.1:28080/realms/adaptive-planner"
    oidc_client_id: str = "planner-web"
    app_origin: str = "http://127.0.0.1:8000"
    ui_origin: str = "http://127.0.0.1:5173"
    environment: str = "local"
    session_hours: int = 8

    @property
    def secure_cookies(self) -> bool:
        return self.environment != "local"

    @model_validator(mode="after")
    def production_https(self):
        if self.environment != "local" and any(
            not url.startswith("https://")
            for url in (self.oidc_issuer, self.app_origin, self.ui_origin)
        ):
            raise ValueError("Non-local deployments require HTTPS origins and OIDC issuer")
        return self

    @model_validator(mode="after")
    def database_parts(self):
        if self.database_host:
            if not self.database_password:
                raise ValueError("Database host requires a secret password")
            self.database_url = URL.create(
                "postgresql+psycopg",
                username=self.database_username,
                password=self.database_password.get_secret_value(),
                host=self.database_host,
                database=self.database_name,
                query={"sslmode": self.database_sslmode},
            ).render_as_string(hide_password=False)
        return self

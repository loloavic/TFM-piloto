from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    internal_api_token: SecretStr | None = None
    session_ttl_seconds: int = Field(default=1800, ge=1, le=86400)
    session_cleanup_interval_seconds: int = Field(default=30, ge=1, le=300)
    session_max_count: int = Field(default=256, ge=1, le=10000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

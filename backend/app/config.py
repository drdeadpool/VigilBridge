from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vigil:vigil@localhost:5432/vigil"
    ingest_api_key: str = ""
    read_api_key: str = ""
    log_level: str = "INFO"
    enable_docs: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        # Render Postgres provides postgresql:// or postgres://
        # SQLAlchemy async engine requires postgresql+asyncpg://
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    def validate_runtime_secrets(self) -> None:
        missing = [
            name
            for name, value in (
                ("INGEST_API_KEY", self.ingest_api_key),
                ("READ_API_KEY", self.read_api_key),
            )
            if not value or value == "changeme"
        ]
        if missing:
            raise RuntimeError(
                f"Missing secure runtime configuration: {', '.join(missing)}"
            )


settings = Settings()

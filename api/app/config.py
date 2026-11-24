from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Configuration, read from the environment and the repo-root `.env` file."""

    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    # Dev default is <repo>/data/zetamaxx.db no matter which folder uvicorn starts in.
    database_path: Path = REPO_ROOT / "data" / "zetamaxx.db"

    clerk_secret_key: str = ""
    clerk_api_url: str = "https://api.clerk.com/v1"
    # Origins allowed in the Clerk token's `azp` claim, comma separated.
    allowed_origins: str = "http://localhost:3000"

    backup_dir: Path | None = None

    @field_validator("database_path")
    @classmethod
    def _absolute(cls, v: Path) -> Path:
        return v if v.is_absolute() else (REPO_ROOT / v).resolve()

    @property
    def allowed_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

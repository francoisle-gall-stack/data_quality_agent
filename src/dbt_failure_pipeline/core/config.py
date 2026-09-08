"""Configuration for dbt failure investigator."""

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DBT_DIR = PROJECT_ROOT / "dbt"
DATA_DIR = PROJECT_ROOT / "data"
SCENARIOS_DIR = PROJECT_ROOT / "scenarios"
RUNTIME_DIR = PROJECT_ROOT / ".scenario_runtime"
LOGS_DIR = RUNTIME_DIR / "logs"
INCIDENTS_DIR = RUNTIME_DIR / "incidents"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    duckdb_path: Path = DATA_DIR / "warehouse.duckdb"
    dbt_dir: Path = DBT_DIR
    gemini_model: str = "gemini-3.5-flash"
    google_api_key: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST"),
    )
    github_token: str = ""
    github_repo: str = ""
    max_tool_calls: int = 8
    max_fix_retries: int = 1
    confidence_threshold: float = 0.70


settings = Settings()

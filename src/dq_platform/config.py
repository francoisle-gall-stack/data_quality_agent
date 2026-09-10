"""Centralized configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DBT_DIR = PROJECT_ROOT / "dbt"
QUALITY_SQL_DIR = PROJECT_ROOT / "quality" / "sql_checks"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    duckdb_path: Path = DATA_DIR / "warehouse.duckdb"
    dbt_profiles_dir: Path = DBT_DIR
    dbt_project_dir: Path = DBT_DIR
    gemini_model: str = "gemini-3.5-flash"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    google_api_key: str = ""
    github_repo: str = ""
    github_token: str = ""


settings = Settings()

"""Tool for reading selected dbt model source files."""

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.tools.context_shared import as_json, source_files


def get_dbt_models(model_names: str) -> str:
    """Return source SQL for comma-separated dbt model names."""
    return as_json(source_files(settings.dbt_dir / "models", model_names, "model"))

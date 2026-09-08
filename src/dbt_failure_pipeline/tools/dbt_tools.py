"""dbt source-code tool used by the correction agent."""

from __future__ import annotations

import json

from dbt_failure_pipeline.core.config import settings


def get_model_sql(model_name: str) -> str:
    """Return source SQL file path and content for a dbt model."""
    for path in settings.dbt_dir.rglob(f"{model_name}.sql"):
        if "target" not in path.parts and "patches" not in path.parts:
            return json.dumps(
                {
                    "path": str(path.relative_to(settings.dbt_dir.parent)),
                    "sql": path.read_text(encoding="utf-8"),
                },
                indent=2,
            )
    return json.dumps({"error": f"Model {model_name}.sql not found"})

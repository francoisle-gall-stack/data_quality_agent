"""Read-only dbt model tools."""

from __future__ import annotations

import json
from pathlib import Path

from dbt_failure_pipeline.core.config import settings


def get_dbt_model(model: str) -> str:
    """Return the file path and source SQL for a dbt model name."""
    model_name = Path(model).stem
    matches = list((settings.dbt_dir / "models").rglob(f"{model_name}.sql"))

    if not matches:
        return json.dumps({"error": f"Model file {model_name}.sql not found"})
    if len(matches) > 1:
        return json.dumps(
            {
                "error": f"Multiple model files named {model_name}.sql found",
                "matches": [
                    path.relative_to(settings.dbt_dir).as_posix() for path in matches
                ],
            }
        )

    path = matches[0]
    return json.dumps(
        {
            "path": path.relative_to(settings.dbt_dir.parent).as_posix(),
            "sql": path.read_text(encoding="utf-8"),
        }
    )

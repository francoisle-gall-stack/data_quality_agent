"""Read dbt model and source documentation for business Q&A."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from dq_platform.config import DBT_DIR


def get_dbt_schema_yml(model_names: str = "") -> str:
    """Return documented dbt models, columns, and raw sources."""
    project_dir = Path(DBT_DIR)
    names = {name.strip() for name in model_names.split(",") if name.strip()}
    result: dict[str, list[dict]] = {"models": [], "sources": []}
    for path in [project_dir / "models" / "schema.yml", project_dir / "models" / "0_staging" / "_sources.yml"]:
        if not path.exists():
            continue
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        key = "models" if "models" in document else "sources"
        for item in document.get(key, []):
            if not names or item.get("name") in names:
                result[key].append(item)
    return json.dumps(result, ensure_ascii=False)

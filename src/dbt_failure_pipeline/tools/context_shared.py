"""Shared read-only helpers for context collection tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.deterministic.investigation.context.diagnostic import (
    get_failed_nodes,
    load_diagnostic,
)
from dbt_failure_pipeline.deterministic.investigation.context.manifest import (
    load_filtered_manifest,
)


def as_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def failed_ids(failed_node_ids: str = "") -> list[str]:
    if failed_node_ids.strip():
        return [item.strip() for item in failed_node_ids.split(",") if item.strip()]
    diagnostic = load_diagnostic(settings.dbt_dir / "target")
    return [node["unique_id"] for node in get_failed_nodes(diagnostic)]


def filtered_manifest(failed_node_ids: str = "") -> dict[str, Any]:
    return load_filtered_manifest(
        settings.dbt_dir / "target",
        failed_ids(failed_node_ids),
    )


def source_files(directory: Path, names: str, kind: str) -> dict[str, Any]:
    requested = [item.strip() for item in names.split(",") if item.strip()]
    if not requested:
        return {"error": f"Provide at least one {kind} name"}

    result: dict[str, Any] = {}
    for name in requested:
        stem = Path(name).stem
        matches = list(directory.rglob(f"{stem}.sql"))
        if not matches:
            result[name] = {"error": f"{kind.capitalize()} file {stem}.sql not found"}
        elif len(matches) > 1:
            result[name] = {
                "error": f"Multiple {kind} files named {stem}.sql found",
                "matches": [
                    path.relative_to(settings.dbt_dir.parent).as_posix()
                    for path in matches
                ],
            }
        else:
            path = matches[0]
            result[stem] = {
                "path": path.relative_to(settings.dbt_dir.parent).as_posix(),
                "sql": path.read_text(encoding="utf-8"),
            }
    return result

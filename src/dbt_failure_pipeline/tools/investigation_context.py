"""Deterministic four-source context for the investigation agent."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from dbt_failure_pipeline.core.config import PROJECT_ROOT, settings
from dbt_failure_pipeline.core.models import InvestigationContext


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required artifact not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve_dbt_path(relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("dbt/"):
        return PROJECT_ROOT / normalized
    return settings.dbt_dir / normalized


def _git_context(file_path: str, commits: int = 5) -> dict[str, Any]:
    """Collect recent working-tree and commit history for one source file."""
    commands = {
        "working_tree_diff": ["git", "diff", "HEAD", "--", file_path],
        "recent_commits": [
            "git",
            "log",
            f"-n{commits}",
            "--format=%H%x09%ad%x09%s",
            "--date=iso",
            "--",
            file_path,
        ],
        "recent_patches": [
            "git",
            "log",
            f"-n{commits}",
            "--format=",
            "-p",
            "--",
            file_path,
        ],
    }
    result: dict[str, Any] = {"file_path": file_path}
    for name, command in commands.items():
        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            result[name] = (completed.stdout or "")[:8000] or "(none)"
            if completed.returncode != 0 and completed.stderr:
                result[f"{name}_error"] = completed.stderr[:500]
        except (OSError, subprocess.SubprocessError) as exc:
            result[name] = f"(unavailable: {exc})"
    return result


def build_investigation_context() -> InvestigationContext:
    """Build context from diagnostic, filtered manifest, compiled SQL, and Git."""
    target_dir = settings.dbt_dir / "target"
    diagnostic = _load_json(target_dir / "diagnostic.json")
    failed_nodes = diagnostic.get("failed_nodes", [])
    if not failed_nodes:
        raise ValueError("diagnostic.json contains no failed node")

    failed = failed_nodes[0]
    failed_id = failed.get("unique_id", "")
    if not failed_id:
        raise ValueError("diagnostic.json failed node has no unique_id")

    manifest = _load_json(target_dir / "manifest.json")
    all_nodes: dict[str, Any] = {
        **manifest.get("nodes", {}),
        **manifest.get("sources", {}),
    }
    failed_manifest_node = all_nodes.get(failed_id)
    if not failed_manifest_node:
        raise ValueError(f"Failed node {failed_id} not found in manifest.json")

    parent_ids = failed_manifest_node.get("depends_on", {}).get("nodes", [])
    selected_ids = [failed_id, *[node_id for node_id in parent_ids if node_id in all_nodes]]
    selected_manifest = {node_id: all_nodes[node_id] for node_id in selected_ids}

    compiled_sql: dict[str, dict[str, str]] = {}
    for node_id, node in selected_manifest.items():
        compiled_path = node.get("compiled_path")
        if not compiled_path:
            compiled_sql[node_id] = {"error": "compiled_path missing from manifest"}
            continue
        path = _resolve_dbt_path(compiled_path)
        if not path.exists():
            compiled_sql[node_id] = {
                "path": _repo_relative(path),
                "error": "compiled SQL file not found",
            }
            continue
        compiled_sql[node_id] = {
            "path": _repo_relative(path),
            "sql": path.read_text(encoding="utf-8"),
        }

    source_path = failed.get("file_path") or failed_manifest_node.get("original_file_path", "")
    normalized_source = source_path.replace("\\", "/")
    git_path = (
        f"dbt/{normalized_source}"
        if normalized_source.startswith(("models/", "tests/", "macros/"))
        else normalized_source
    )
    git = _git_context(git_path)
    return InvestigationContext(
        diagnostic=diagnostic,
        manifest={"nodes": selected_manifest},
        compiled_sql=compiled_sql,
        git=git,
    )

"""Récupération déterministe des SQL compilés par dbt."""

from __future__ import annotations

from pathlib import Path
from typing import Any

def _repo_relative(path: Path, project_root: Path) -> str:
    """Convertit un chemin absolu en chemin relatif au dépôt."""
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _resolve_dbt_path(relative_path: str, dbt_dir: Path, project_root: Path) -> Path:
    """Résout un chemin d'artefact dbt, relatif au dépôt ou au projet dbt."""
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("dbt/"):
        return project_root / normalized
    return dbt_dir / normalized


def load_compiled_sql(
    selected_manifest: dict[str, Any],
    dbt_dir: Path,
    project_root: Path,
) -> dict[str, dict[str, str]]:
    """Charge les SQL compilés des nœuds conservés dans le manifest filtré."""
    compiled_sql: dict[str, dict[str, str]] = {}
    for node_id, node in selected_manifest["nodes"].items():
        compiled_path = node.get("compiled_path")
        node_path = str(node.get("path") or "")
        package_name = str(node.get("package_name") or "")
        model_path = node_path if node_path.startswith("models/") else f"models/{node_path}"
        candidates = [
            _resolve_dbt_path(compiled_path, dbt_dir, project_root)
            if compiled_path
            else dbt_dir / "target" / "compiled" / package_name / model_path,
            dbt_dir / "target" / "compiled" / package_name / model_path,
            dbt_dir / "target" / "run" / package_name / model_path,
        ]
        path = next((candidate for candidate in candidates if candidate.exists()), None)
        if path is None:
            compiled_sql[node_id] = {
                "error": "fichier SQL compilé introuvable",
                "candidates": ", ".join(str(candidate) for candidate in candidates),
            }
            continue

        compiled_sql[node_id] = {
            "path": _repo_relative(path, project_root),
            "sql": path.read_text(encoding="utf-8"),
        }
    return compiled_sql

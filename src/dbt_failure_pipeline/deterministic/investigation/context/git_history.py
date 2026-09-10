"""Récupération déterministe du diff et de l'historique Git."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _git_path(source_path: str) -> str:
    """Construit le chemin Git à partir du chemin dbt du modèle."""
    normalized = source_path.replace("\\", "/")
    if normalized.startswith(("models/", "tests/", "macros/")):
        return f"dbt/{normalized}"
    return normalized


def load_git_history(
    source_path: str,
    project_root: Path,
    commits: int = 5,
) -> dict[str, Any]:
    """Retourne le diff courant, les commits et les patchs récents du fichier."""
    file_path = _git_path(source_path)
    commands = {
        "working_tree_diff": ["git", "diff", "HEAD", "--", file_path],
        "recent_commits": [
            "git", "log", f"-n{commits}", "--format=%H%x09%ad%x09%s",
            "--date=iso", "--", file_path,
        ],
        "recent_patches": [
            "git", "log", f"-n{commits}", "--format=", "-p", "--", file_path,
        ],
    }
    result: dict[str, Any] = {"file_path": file_path}
    for name, command in commands.items():
        try:
            completed = subprocess.run(
                command,
                cwd=project_root,
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

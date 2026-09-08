"""Patch proposal tool (Correction Agent only)."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

from dbt_failure_pipeline.core.config import PROJECT_ROOT, settings
from dbt_failure_pipeline.core.exceptions import PatchNotAllowedError

ALLOWLIST_ROOTS = [
    settings.dbt_dir / "models",
    settings.dbt_dir / "tests",
    settings.dbt_dir / "macros",
]


def _is_allowed(path: Path) -> bool:
    resolved = path.resolve()
    return any(str(resolved).startswith(str(root.resolve())) for root in ALLOWLIST_ROOTS)


def propose_patch(
    file_path: str,
    patched_content: str,
    summary: str,
) -> str:
    """Propose a unified diff for a single allowlisted file."""
    target = (PROJECT_ROOT / file_path).resolve()
    if not _is_allowed(target):
        raise PatchNotAllowedError(f"File {file_path} is not in allowlist")
    if not target.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    original = target.read_text(encoding="utf-8")
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        patched_content.splitlines(keepends=True),
        fromfile=file_path,
        tofile=file_path,
    )
    diff_text = "".join(diff)
    return json.dumps(
        {
            "file_path": file_path,
            "summary": summary,
            "diff_unified": diff_text,
            "original_content": original,
            "patched_content": patched_content,
            "status": "proposed",
        },
        indent=2,
    )

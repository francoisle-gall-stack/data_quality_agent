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
    """
    - Return whether a path is inside an allowed dbt directory.
    - Vérifie qu’un fichier se trouve dans un répertoire dbt autorisé.
    """
    resolved = path.resolve()
    return any(str(resolved).startswith(str(root.resolve())) for root in ALLOWLIST_ROOTS)


def propose_patch(
    file_path: str,
    patched_content: str,
    summary: str,
) -> str:
    """Build a JSON patch proposal for one allowlisted dbt file.

    Args:
        file_path: Relative path of the file to patch.
        patched_content: Complete file content after the proposed correction.
        summary: Short description of the proposed correction.

    Returns:
        A JSON string containing the original content, patched content, and
        unified diff, or an error when the target file does not exist.

    Raises:
        PatchNotAllowedError: If ``file_path`` is outside the allowed dbt
            models, tests, and macros directories.
    """
    relative_path = Path(file_path)
    if relative_path.parts and relative_path.parts[0] in {"models", "tests", "macros"}:
        target = (settings.dbt_dir / relative_path).resolve()
    else:
        target = (PROJECT_ROOT / relative_path).resolve()
    if not _is_allowed(target):
        raise PatchNotAllowedError(f"File {file_path} is not in allowlist")
    if not target.exists():
        return json.dumps({"error": f"File not found: {file_path}"})

    canonical_path = target.relative_to(PROJECT_ROOT).as_posix()
    original = target.read_text(encoding="utf-8")
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        patched_content.splitlines(keepends=True),
        fromfile=canonical_path,
        tofile=canonical_path,
    )
    diff_text = "".join(diff)
    return json.dumps(
        {
            "file_path": canonical_path,
            "summary": summary,
            "diff_unified": diff_text,
            "original_content": original,
            "patched_content": patched_content,
            "status": "proposed",
        },
        indent=2,
    )

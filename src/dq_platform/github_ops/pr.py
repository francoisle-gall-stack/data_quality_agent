"""GitHub PR operations (post human approval)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from dq_platform.config import PROJECT_ROOT


def create_branch(branch_name: str) -> None:
    subprocess.run(["git", "checkout", "-b", branch_name], cwd=PROJECT_ROOT, check=True)


def apply_patch(file_path: Path, content: str) -> None:
    file_path.write_text(content, encoding="utf-8")


def run_dbt_test() -> bool:
    result = subprocess.run(
        ["dbt", "test", "--project-dir", "dbt", "--profiles-dir", "dbt"],
        cwd=PROJECT_ROOT,
        capture_output=True,
    )
    return result.returncode == 0


def create_pull_request(title: str, body: str) -> str:
    result = subprocess.run(
        ["gh", "pr", "create", "--title", title, "--body", body],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()

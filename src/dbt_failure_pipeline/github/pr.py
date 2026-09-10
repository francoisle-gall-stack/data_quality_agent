"""GitHub PR operations."""

from __future__ import annotations

import subprocess

from dbt_failure_pipeline.core.config import PROJECT_ROOT, settings


def create_pull_request(title: str, body: str) -> str:
    if not settings.github_token:
        return "PR skipped: GITHUB_TOKEN not configured (dry-run mode)"

    env = {**dict(__import__("os").environ), "GH_TOKEN": settings.github_token}
    proc = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            "main",
            "--title",
            title,
            "--body",
            body,
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()

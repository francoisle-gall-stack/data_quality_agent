"""dbt command execution (deterministic)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from dbt_failure_pipeline.core.config import LOGS_DIR, settings


@dataclass
class DbtRunResult:
    success: bool
    returncode: int
    stdout: str
    stderr: str
    command: str
    log_path: Path


def run_dbt_command(command: list[str]) -> DbtRunResult:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / f"dbt_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.log"
    env = {
        **dict(__import__("os").environ),
        "DUCKDB_PATH": str(settings.duckdb_path),
        "DBT_PROFILES_DIR": str(settings.dbt_dir),
    }
    proc = subprocess.run(
        command,
        cwd=settings.dbt_dir.parent,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    full_log = f"STDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
    log_path.write_text(full_log, encoding="utf-8")
    return DbtRunResult(
        success=proc.returncode == 0,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        command=" ".join(command),
        log_path=log_path,
    )


def run_dbt_build() -> DbtRunResult:
    return run_dbt_command(
        [
            "dbt",
            "build",
            "--project-dir",
            str(settings.dbt_dir),
            "--profiles-dir",
            str(settings.dbt_dir),
        ]
    )


def run_dbt_compile() -> DbtRunResult:
    return run_dbt_command(
        [
            "dbt",
            "compile",
            "--project-dir",
            str(settings.dbt_dir),
            "--profiles-dir",
            str(settings.dbt_dir),
        ]
    )


def run_dbt_test() -> DbtRunResult:
    return run_dbt_command(
        [
            "dbt",
            "test",
            "--project-dir",
            str(settings.dbt_dir),
            "--profiles-dir",
            str(settings.dbt_dir),
        ]
    )

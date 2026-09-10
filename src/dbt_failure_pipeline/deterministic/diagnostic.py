"""Deterministic dbt failure diagnostic from run_results.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.core.models import DbtDiagnostic, FailedNode

_FILE_PATH_FROM_MESSAGE = re.compile(r"\((models[/\\][^)]+)\)")


def _extract_file_path(message: str | None) -> str:
    """Extract model file path from a dbt error message."""
    if not message:
        return ""
    match = _FILE_PATH_FROM_MESSAGE.search(message)
    return match.group(1) if match else ""


def extract_dbt_errors(
    run_results_path: Path | str,
    output_path: Path | str | None = None,
) -> DbtDiagnostic:
    """Build a structured diagnostic from dbt run_results.json.

    Only ``run_results.json`` is read. Failed nodes have status ``error`` or ``fail``.
    """
    with open(run_results_path, encoding="utf-8") as f:
        data = json.load(f)

    invocation_cmd = data.get("args", {}).get("invocation_command", "")
    if invocation_cmd.startswith("dbt "):
        command_executed = invocation_cmd
    else:
        command_executed = f"dbt {invocation_cmd}" if invocation_cmd else "Inconnue"

    failed_nodes: list[FailedNode] = []
    for result in data.get("results", []):
        status = result.get("status")
        if status not in ("error", "fail"):
            continue

        unique_id = result.get("unique_id", "")
        parts = unique_id.split(".")
        node_type = parts[0] if parts else "unknown"
        node_name = parts[-1] if len(parts) > 1 else unique_id

        failed_nodes.append(
            FailedNode(
                node_type=node_type,
                unique_id=unique_id,
                node_name=node_name,
                file_path=_extract_file_path(result.get("message")),
                error_message=result.get("message"),
            )
        )

    diagnostic = DbtDiagnostic(
        command_executed=command_executed,
        has_errors=len(failed_nodes) > 0,
        failed_nodes=failed_nodes,
    )

    if output_path is not None:
        Path(output_path).write_text(
            diagnostic.model_dump_json(indent=2),
            encoding="utf-8",
        )

    return diagnostic


def run_diagnostic(output_path: Path | str | None = None) -> DbtDiagnostic:
    """Run diagnostic using run_results.json from the default dbt target directory."""
    target_dir = settings.dbt_dir / "target"
    run_results_path = target_dir / "run_results.json"
    resolved_output = Path(output_path) if output_path else target_dir / "diagnostic.json"

    return extract_dbt_errors(
        run_results_path=run_results_path,
        output_path=resolved_output,
    )


def run_diagnostic_cli() -> None:
    """CLI entry point — print diagnostic JSON to stdout."""
    diagnostic = run_diagnostic()
    print(diagnostic.model_dump_json(indent=2))

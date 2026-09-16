"""HTTP-facing orchestration for the dbt failure pipeline dashboard."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.core.models import IncidentStatus, InvestigationRecord
from dbt_failure_pipeline.core.state import save_incident, set_current_incident_id
from dbt_failure_pipeline.deterministic import (
    extract_dbt_error_text,
    prioritize_failed_nodes_for_scenario,
    run_dbt_build,
    run_dbt_full_refresh,
    run_diagnostic,
)
from dbt_failure_pipeline.orchestration.fix_pipeline import run_fix_pipeline
from dbt_failure_pipeline.orchestration.pipeline import run_correction, run_investigation
from dbt_failure_pipeline.scenarios.manager import (
    activate_scenario,
    get_active_scenario,
    get_scenario_info,
    list_scenarios,
    reset_scenario,
)


@dataclass
class PipelineRun:
    run_id: str
    scenario_id: str
    status: str = "queued"
    incident_id: str | None = None
    record: InvestigationRecord | None = None
    error: str | None = None
    reset_result: dict[str, Any] = field(default_factory=dict)
    activation_result: dict[str, Any] = field(default_factory=dict)
    full_refresh_result: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "status": self.status,
            "incident_id": self.incident_id,
            "record": self.record.model_dump(mode="json") if self.record else None,
            "error": self.error,
            "active_scenario": get_active_scenario(),
            "reset_result": self.reset_result,
            "activation_result": self.activation_result,
            "full_refresh_result": self.full_refresh_result,
        }


_runs: dict[str, PipelineRun] = {}


def scenarios() -> list[dict[str, Any]]:
    return [get_scenario_info(scenario_id) for scenario_id in list_scenarios()]


def get_run(run_id: str) -> PipelineRun | None:
    return _runs.get(run_id)


def start_run(scenario_id: str, reset_before_activate: bool) -> PipelineRun:
    run = PipelineRun(run_id=f"RUN-{uuid.uuid4().hex[:8].upper()}", scenario_id=scenario_id)
    _runs[run.run_id] = run
    asyncio.create_task(_execute(run, reset_before_activate))
    return run


async def _execute(run: PipelineRun, reset_before_activate: bool) -> None:
    try:
        run.status = "running"
        if reset_before_activate:
            run.reset_result = reset_scenario()
        run.activation_result = activate_scenario(run.scenario_id)
        if run.scenario_id == "SC037":
            full_refresh = run_dbt_full_refresh()
            run.full_refresh_result = {
                "success": full_refresh.success,
                "command": full_refresh.command,
                "log_path": str(full_refresh.log_path),
            }
            if not full_refresh.success:
                run.status = "error"
                run.error = "The SC037 full-refresh preparation failed."
                return
        result = run_dbt_build()
        run_results_path = settings.dbt_dir / "target" / "run_results.json"
        if result.success:
            run.status = "completed"
            run.error = "dbt build succeeded: this scenario did not produce a failure."
            return
        if run_results_path.exists():
            diagnostic = run_diagnostic()
        else:
            diagnostic = extract_dbt_error_text(
                f"{result.stdout}\n{result.stderr}",
                command_executed=result.command,
            )
        diagnostic = prioritize_failed_nodes_for_scenario(diagnostic, run.scenario_id)
        if not diagnostic.has_errors:
            run.status = "completed"
            run.error = "dbt build failed but no error node was found."
            return

        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        record = InvestigationRecord(
            incident_id=incident_id,
            scenario_id=run.scenario_id,
            status=IncidentStatus.OPEN,
            diagnostic=diagnostic,
        )
        save_incident(record)
        set_current_incident_id(incident_id)
        run.incident_id = incident_id
        record = await run_investigation(incident_id)
        if record.status == IncidentStatus.INVESTIGATED:
            record = await run_correction(incident_id)
        run.record = record
        run.status = record.status.value
    except Exception as exc:
        run.status = "error"
        run.error = str(exc)


async def approve_run(run_id: str) -> PipelineRun:
    run = _runs[run_id]
    if not run.incident_id:
        run.status = "error"
        run.error = "No incident is available for approval."
        return run
    run.status = "fixing"
    asyncio.create_task(_execute_approval(run))
    return run


async def _execute_approval(run: PipelineRun) -> None:
    try:
        run.record = await asyncio.to_thread(
            run_fix_pipeline, run.incident_id, human_approved=True
        )
        run.status = run.record.status.value
    except Exception as exc:
        run.status = "error"
        run.error = str(exc)

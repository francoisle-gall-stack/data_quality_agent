"""Evaluation runner — scenario ground truth comparison."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

import yaml

from dbt_failure_pipeline.core.config import SCENARIOS_DIR
from dbt_failure_pipeline.deterministic import run_diagnostic, run_dbt_build
from dbt_failure_pipeline.evaluation.classification import classify_diagnostic
from dbt_failure_pipeline.evaluation.metrics import classification_match, root_cause_file_match
from dbt_failure_pipeline.orchestration.pipeline import run_investigation
from dbt_failure_pipeline.scenarios.manager import activate_scenario, list_scenarios, reset_scenario


def _load_ground_truth(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / scenario_id / "ground_truth.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


async def evaluate_scenario(scenario_id: str, use_agents: bool = False) -> dict:
    reset_scenario()
    activate_scenario(scenario_id)
    build = run_dbt_build()
    if build.success:
        reset_scenario()
        return {"scenario_id": scenario_id, "failed": True, "reason": "dbt build succeeded"}

    diagnostic = run_diagnostic()
    if not diagnostic.has_errors:
        reset_scenario()
        return {"scenario_id": scenario_id, "failed": True, "reason": "no errors in run_results"}

    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    gt = _load_ground_truth(scenario_id)
    result = {
        "scenario_id": scenario_id,
        "incident_id": incident_id,
        "error_category": classify_diagnostic(diagnostic).value,
        "classification_match": classification_match(diagnostic, gt.get("error_type", "")),
    }

    if use_agents:
        from dbt_failure_pipeline.core.models import IncidentStatus, InvestigationRecord
        from dbt_failure_pipeline.core.state import save_incident

        record = InvestigationRecord(
            incident_id=incident_id,
            scenario_id=scenario_id,
            status=IncidentStatus.OPEN,
            diagnostic=diagnostic,
        )
        save_incident(record)
        record = await run_investigation(incident_id)
        result["root_cause_file_match"] = root_cause_file_match(
            record, gt.get("expected_fix", {}).get("file", "")
        )
        result["status"] = record.status.value

    reset_scenario()
    return result


async def run_all(use_agents: bool = False) -> list[dict]:
    results = []
    for sid in list_scenarios():
        results.append(await evaluate_scenario(sid, use_agents=use_agents))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate dbt failure scenarios")
    parser.add_argument("--scenario", help="Single scenario ID")
    parser.add_argument("--use-agents", action="store_true", help="Run ADK agents (requires API key)")
    args = parser.parse_args()

    if args.scenario:
        results = [asyncio.run(evaluate_scenario(args.scenario, use_agents=args.use_agents))]
    else:
        results = asyncio.run(run_all(use_agents=args.use_agents))

    print(json.dumps(results, indent=2))
    passed = sum(1 for r in results if r.get("classification_match"))
    print(f"\nClassification match: {passed}/{len(results)}")


if __name__ == "__main__":
    main()

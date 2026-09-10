#!/usr/bin/env python3
"""Activate a failure scenario, run dbt build, and create an incident."""

import argparse
import sys
import uuid

from dbt_failure_pipeline.core.models import IncidentStatus, InvestigationRecord
from dbt_failure_pipeline.core.state import save_incident, set_current_incident_id
from dbt_failure_pipeline.deterministic import run_diagnostic, run_dbt_build
from dbt_failure_pipeline.scenarios.manager import activate_scenario, reset_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Activate dbt failure scenario")
    parser.add_argument("scenario_id", help="Scenario ID e.g. SC001")
    parser.add_argument("--reset-first", action="store_true", help="Reset active scenario before activate")
    args = parser.parse_args()

    if args.reset_first:
        reset_scenario()

    info = activate_scenario(args.scenario_id)
    print(f"Activated {args.scenario_id}: patched {info['patched_files']}")

    result = run_dbt_build()
    if result.success:
        print("dbt build succeeded — scenario did not produce a failure.")
        sys.exit(1)

    diagnostic = run_diagnostic()
    if not diagnostic.has_errors:
        print("dbt build failed but no error nodes found in run_results.json.")
        sys.exit(1)

    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    record = InvestigationRecord(
        incident_id=incident_id,
        scenario_id=args.scenario_id,
        status=IncidentStatus.OPEN,
        diagnostic=diagnostic,
    )
    save_incident(record)
    set_current_incident_id(incident_id)
    print(diagnostic.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

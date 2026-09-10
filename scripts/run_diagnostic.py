#!/usr/bin/env python3
"""Extract deterministic diagnostic from dbt run_results.json."""

from dbt_failure_pipeline.deterministic import run_diagnostic


def main() -> None:
    diagnostic = run_diagnostic()
    print(diagnostic.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

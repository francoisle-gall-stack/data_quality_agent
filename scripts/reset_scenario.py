#!/usr/bin/env python3
"""Reset active scenario to baseline files."""

from dbt_failure_pipeline.scenarios.manager import reset_scenario

if __name__ == "__main__":
    print(reset_scenario())

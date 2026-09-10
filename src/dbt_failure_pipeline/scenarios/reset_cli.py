"""CLI to reset active scenario."""

from dbt_failure_pipeline.scenarios.manager import reset_scenario


def main() -> None:
    print(reset_scenario())

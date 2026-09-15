"""Tool for reading the dbt diagnostic artifact."""

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.deterministic.investigation.context.diagnostic import (
    load_diagnostic,
)
from dbt_failure_pipeline.tools.context_shared import as_json


def get_dbt_diagnostic() -> str:
    """Return the dbt diagnostic artifact for the current failure."""
    return as_json(load_diagnostic(settings.dbt_dir / "target"))

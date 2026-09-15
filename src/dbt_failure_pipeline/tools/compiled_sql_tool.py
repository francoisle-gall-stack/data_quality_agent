"""Tool for reading compiled dbt SQL."""

from dbt_failure_pipeline.core.config import PROJECT_ROOT, settings
from dbt_failure_pipeline.deterministic.investigation.context.compiled_sql import (
    load_compiled_sql,
)
from dbt_failure_pipeline.tools.context_shared import as_json, filtered_manifest


def get_dbt_compiled_sql(failed_node_ids: str = "") -> str:
    """Return compiled SQL for failed, upstream, and downstream nodes."""
    manifest = filtered_manifest(failed_node_ids)
    return as_json(
        load_compiled_sql(
            manifest,
            dbt_dir=settings.dbt_dir,
            project_root=PROJECT_ROOT,
        )
    )

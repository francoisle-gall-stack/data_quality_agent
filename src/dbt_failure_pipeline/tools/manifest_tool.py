"""Tool for reading the filtered dbt manifest and lineage."""

from dbt_failure_pipeline.tools.context_shared import as_json, filtered_manifest


def get_dbt_manifest(failed_node_ids: str = "") -> str:
    """Return the filtered manifest and transitive lineage for failed nodes."""
    return as_json(filtered_manifest(failed_node_ids))

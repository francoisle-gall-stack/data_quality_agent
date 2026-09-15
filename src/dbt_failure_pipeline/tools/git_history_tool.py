"""Tool for reading Git history for relevant dbt files."""

from dbt_failure_pipeline.core.config import PROJECT_ROOT
from dbt_failure_pipeline.deterministic.investigation.context.git_history import (
    load_git_history,
)
from dbt_failure_pipeline.tools.context_shared import as_json, filtered_manifest


def get_dbt_git_history(failed_node_ids: str = "") -> str:
    """Return current diffs and recent Git history for manifest nodes."""
    manifest = filtered_manifest(failed_node_ids)
    history = {
        unique_id: load_git_history(
            node.get("original_file_path", node.get("file_path", "")),
            project_root=PROJECT_ROOT,
        )
        for unique_id, node in manifest["nodes"].items()
        if node.get("original_file_path") or node.get("file_path")
    }
    return as_json(history)

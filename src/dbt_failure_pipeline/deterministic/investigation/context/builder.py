"""Assemblage déterministe des quatre sources du contexte d'investigation."""

from __future__ import annotations

from dbt_failure_pipeline.core.config import PROJECT_ROOT, settings
from dbt_failure_pipeline.core.models import InvestigationContext
from dbt_failure_pipeline.deterministic.investigation.context.compiled_sql import (
    load_compiled_sql,
)
from dbt_failure_pipeline.deterministic.investigation.context.diagnostic import (
    get_failed_nodes,
    load_diagnostic,
)
from dbt_failure_pipeline.deterministic.investigation.context.git_history import (
    load_git_history,
)
from dbt_failure_pipeline.deterministic.investigation.context.manifest import (
    load_filtered_manifest,
)


def build_investigation_context() -> InvestigationContext:
    """Assemble diagnostic, manifest filtré, SQL compilés et historique Git."""
    target_dir = settings.dbt_dir / "target"
    diagnostic = load_diagnostic(target_dir)
    failed_nodes = get_failed_nodes(diagnostic)
    failed_ids = [node["unique_id"] for node in failed_nodes]
    selected_manifest = load_filtered_manifest(target_dir, failed_ids)
    compiled_sql = load_compiled_sql(
        selected_manifest,
        dbt_dir=settings.dbt_dir,
        project_root=PROJECT_ROOT,
    )
    git = {
        node["unique_id"]: load_git_history(
            node.get("file_path", ""),
            project_root=PROJECT_ROOT,
        )
        for node in failed_nodes
    }
    return InvestigationContext(
        diagnostic=diagnostic,
        manifest=selected_manifest,
        compiled_sql=compiled_sql,
        git=git,
        lineage=selected_manifest["lineage"],
    )

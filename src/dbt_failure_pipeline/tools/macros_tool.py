"""Tool for reading selected or all dbt macro source files."""

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.tools.context_shared import as_json, source_files


def get_dbt_macros(macro_names: str = "") -> str:
    """Return named dbt macros, or all macros when no names are provided."""
    directory = settings.dbt_dir / "macros"
    if not macro_names.strip():
        return as_json(
            {
                path.stem: {
                    "path": path.relative_to(settings.dbt_dir.parent).as_posix(),
                    "sql": path.read_text(encoding="utf-8"),
                }
                for path in directory.rglob("*.sql")
            }
        )
    return as_json(source_files(directory, macro_names, "macro"))

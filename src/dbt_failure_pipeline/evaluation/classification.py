"""Error classification for evaluation and pipeline guards."""

from __future__ import annotations

from dbt_failure_pipeline.core.models import DbtDiagnostic, ErrorCategory


def classify_error(message: str) -> ErrorCategory:
    """Classify a dbt error message into a category."""
    lower = message.lower()
    if any(x in lower for x in ["locked", "permission", "io error", "cannot open file"]):
        return ErrorCategory.INFRASTRUCTURE
    if any(x in lower for x in ["profiles.yml", "dbt_profile", "env_var"]):
        return ErrorCategory.CONFIG_ERROR
    if "configured to fail" in lower or ("got" in lower and "result" in lower):
        return ErrorCategory.DBT_TEST_FAILURE
    if "test" in lower and ("fail" in lower or "failed" in lower):
        return ErrorCategory.DBT_TEST_FAILURE
    if any(
        x in lower
        for x in ["not found", "does not exist", "referenced column", "does not have a column"]
    ) and any(x in lower for x in ["column", "table", "field", "named"]):
        return ErrorCategory.SCHEMA_CHANGE
    if any(x in lower for x in ["depends on", "upstream", "skipped due to"]):
        return ErrorCategory.DEPENDENCY_ERROR
    if any(
        x in lower
        for x in [
            "cast",
            "conversion",
            "invalid input",
            "could not convert",
            "divide by zero",
            "division by zero",
        ]
    ):
        return ErrorCategory.DATA_ERROR
    if any(
        x in lower
        for x in [
            "binder error",
            "syntax error",
            "parser error",
            "catalog error",
            "catalog exception",
            "invalid function",
        ]
    ):
        return ErrorCategory.SQL_COMPILATION
    return ErrorCategory.UNKNOWN


def classify_diagnostic(diagnostic: DbtDiagnostic) -> ErrorCategory:
    """Classify the primary failure from a diagnostic."""
    node = diagnostic.primary_failed_node
    if node is None or not node.error_message:
        return ErrorCategory.UNKNOWN
    return classify_error(node.error_message)


def is_auto_fixable(diagnostic: DbtDiagnostic) -> bool:
    """Return whether the diagnostic error is likely auto-fixable."""
    category = classify_diagnostic(diagnostic)
    return category not in (ErrorCategory.INFRASTRUCTURE, ErrorCategory.CONFIG_ERROR)

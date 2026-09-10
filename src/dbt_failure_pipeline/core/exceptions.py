"""Custom exceptions."""


class DbtFailureAgentError(Exception):
    """Base error for dbt failure agent."""


class ScenarioNotFoundError(DbtFailureAgentError):
    """Scenario ID not found."""


class PatchNotAllowedError(DbtFailureAgentError):
    """Patch targets a file outside allowlist."""


class IncidentNotFoundError(DbtFailureAgentError):
    """Incident record not found."""

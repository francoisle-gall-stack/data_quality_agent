"""Pydantic models for dbt failure investigation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    SQL_COMPILATION = "sql_compilation"
    SCHEMA_CHANGE = "schema_change"
    DATA_ERROR = "data_error"
    DBT_TEST_FAILURE = "dbt_test_failure"
    DEPENDENCY_ERROR = "dependency_error"
    CONFIG_ERROR = "config_error"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    INVESTIGATED = "investigated"
    AWAITING_APPROVAL = "awaiting_approval"
    FIXING = "fixing"
    NEEDS_HUMAN = "needs_human"
    RESOLVED = "resolved"
    PR_CREATED = "pr_created"


class FailedNode(BaseModel):
    node_type: str
    unique_id: str
    node_name: str
    file_path: str = ""
    error_message: str | None = None


class DbtDiagnostic(BaseModel):
    command_executed: str
    has_errors: bool
    failed_nodes: list[FailedNode] = Field(default_factory=list)

    @property
    def primary_failed_node(self) -> FailedNode | None:
        return self.failed_nodes[0] if self.failed_nodes else None


class RootCauseAnalysis(BaseModel):
    error_type: str
    observations: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    root_cause: str
    confidence: float = 0.5
    affected_models: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    proposed_fix: str | None = None
    requires_human_intervention: bool = False


class InvestigationContext(BaseModel):
    """Evidence bundle passed to the investigation agent."""

    diagnostic: dict[str, Any]
    manifest: dict[str, Any]
    compiled_sql: dict[str, dict[str, str]]
    git: dict[str, Any]


class ProposedPatch(BaseModel):
    file_path: str
    summary: str
    diff_unified: str
    original_content: str = ""
    patched_content: str = ""
    confidence: float = 0.5
    tests_to_run: list[str] = Field(default_factory=list)


class InvestigationRecord(BaseModel):
    incident_id: str
    scenario_id: str | None = None
    status: IncidentStatus = IncidentStatus.OPEN
    diagnostic: DbtDiagnostic
    rca: RootCauseAnalysis | None = None
    patch: ProposedPatch | None = None
    investigation_output: str = ""
    correction_output: str = ""
    validation_passed: bool | None = None
    pr_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

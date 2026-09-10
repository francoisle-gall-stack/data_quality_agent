"""Pydantic models for agent I/O."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnomalyEvent(BaseModel):
    anomaly_id: str
    table: str
    metric: str
    observed_value: float
    expected_value: float | None = None
    deviation: float | None = None
    date: str


class EvidenceItem(BaseModel):
    tool: str
    query_or_args: str
    finding: str


class RecommendedFix(BaseModel):
    type: str
    files: list[str] = Field(default_factory=list)
    summary: str


class ConfidenceInfo(BaseModel):
    score: float
    basis: list[str] = Field(default_factory=list)
    residual_risks: list[str] = Field(default_factory=list)


class RootCauseAnalysis(BaseModel):
    what: str
    when: str
    where: str
    why: str
    root_cause: str
    confidence: float
    affected_tables: list[str] = Field(default_factory=list)
    affected_columns: list[str] = Field(default_factory=list)
    affected_period: dict[str, Any] = Field(default_factory=dict)
    business_impact: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    recommended_fix: RecommendedFix | None = None
    confidence_info: ConfidenceInfo | None = None

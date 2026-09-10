"""Tests for the separated investigation and correction stages."""

import json

import pytest

from dbt_failure_pipeline.core.models import (
    DbtDiagnostic,
    FailedNode,
    IncidentStatus,
    InvestigationContext,
    InvestigationRecord,
)
from dbt_failure_pipeline.core.state import save_incident
from dbt_failure_pipeline.orchestration import pipeline


@pytest.mark.asyncio
async def test_investigation_only_makes_one_llm_call(monkeypatch):
    record = InvestigationRecord(
        incident_id="INC-PIPELINE",
        status=IncidentStatus.OPEN,
        diagnostic=DbtDiagnostic(
            command_executed="dbt build",
            has_errors=True,
            failed_nodes=[
                FailedNode(
                    node_type="model",
                    unique_id="model.project.orders",
                    node_name="orders",
                )
            ],
        ),
    )
    save_incident(record)
    calls = []

    async def fake_run_agent(agent, message, app_name, session_id):
        calls.append((agent, app_name, session_id))
        return "confidence: 0.9\nroot_cause: broken join"

    monkeypatch.setattr(pipeline, "setup_langfuse", lambda: False)
    monkeypatch.setattr(pipeline, "flush_langfuse", lambda: None)
    monkeypatch.setattr(pipeline, "run_diagnostic", lambda: record.diagnostic)
    monkeypatch.setattr(pipeline, "is_auto_fixable", lambda diagnostic: True)
    monkeypatch.setattr(pipeline.settings, "google_api_key", "test-key")
    monkeypatch.setattr(
        pipeline,
        "build_investigation_context",
        lambda: InvestigationContext(
            diagnostic=record.diagnostic.model_dump(),
            manifest={"nodes": {}},
            compiled_sql={},
            git={},
        ),
    )
    monkeypatch.setattr(pipeline, "_run_agent", fake_run_agent)

    result = await pipeline.run_investigation(record.incident_id)

    assert result.status == IncidentStatus.INVESTIGATED
    assert len(calls) == 1
    assert calls[0][1] == "dbt_investigation"
    assert not result.correction_output


@pytest.mark.asyncio
async def test_correction_is_a_separate_llm_call(monkeypatch):
    record = InvestigationRecord(
        incident_id="INC-CORRECTION",
        status=IncidentStatus.INVESTIGATED,
        diagnostic=DbtDiagnostic(
            command_executed="dbt build",
            has_errors=True,
            failed_nodes=[
                FailedNode(
                    node_type="model",
                    unique_id="model.project.orders",
                    node_name="orders",
                )
            ],
        ),
        investigation_output="confidence: 0.9\nroot_cause: broken join",
    )
    record.rca = pipeline._build_rca_from_investigation(record.investigation_output)
    save_incident(record)
    calls = []

    async def fake_run_agent(agent, message, app_name, session_id):
        calls.append(app_name)
        return json.dumps(
            {
                "file_path": "dbt/models/orders.sql",
                "summary": "Fix join",
                "diff_unified": "--- a/orders.sql\n+++ b/orders.sql",
                "patched_content": "select 1",
            }
        )

    monkeypatch.setattr(pipeline, "flush_langfuse", lambda: None)
    monkeypatch.setattr(pipeline.settings, "google_api_key", "test-key")
    monkeypatch.setattr(pipeline, "_run_agent", fake_run_agent)

    result = await pipeline.run_correction(record.incident_id)

    assert result.status == IncidentStatus.AWAITING_APPROVAL
    assert calls == ["dbt_correction"]

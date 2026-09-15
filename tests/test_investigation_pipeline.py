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


def test_source_data_issue_requires_human_review():
    assert pipeline._is_source_data_issue(
        "Source data issue: required product records are absent from the catalog."
    )
    assert not pipeline._is_source_data_issue(
        "The investigation considered a source data issue, but the missing macro "
        "is a deterministic model error."
    )
    assert not pipeline._is_source_data_issue(
        "The test found orphan product_id values and a referential integrity problem."
    )
    assert not pipeline._is_source_data_issue(
        "The model has a missing column caused by an incorrect ref()."
    )


def test_context_policy_targets_schema_change_evidence():
    diagnostic = DbtDiagnostic(
        command_executed="dbt build",
        has_errors=True,
        failed_nodes=[
            FailedNode(
                node_type="model",
                unique_id="model.project.orders",
                node_name="orders",
                error_message=(
                    "Runtime Error: Binder Error: relation does not have a "
                    "column named customer_segment"
                ),
            )
        ],
    )

    policy = pipeline._context_tool_policy(diagnostic)

    assert policy["error_category"] == "schema_change"
    assert policy["required"] == [
        "get_dbt_manifest",
        "get_dbt_compiled_sql",
        "get_dbt_git_history",
        "get_dbt_models",
    ]
    assert "get_dbt_macros" in policy["forbidden"]
    assert "get_dbt_diagnostic" in policy["forbidden"]


def test_context_policy_allows_macros_only_for_macro_errors():
    diagnostic = DbtDiagnostic(
        command_executed="dbt compile",
        has_errors=True,
        failed_nodes=[
            FailedNode(
                node_type="model",
                unique_id="model.project.orders",
                node_name="orders",
                error_message="Compilation Error in macro order_revenue",
            )
        ],
    )

    policy = pipeline._context_tool_policy(diagnostic)

    assert "get_dbt_macros" in policy["required"]
    assert "get_dbt_macros" not in policy["forbidden"]


def test_trim_context_removes_manifest_sql_already_collected_as_model():
    context = InvestigationContext(
        manifest={
            "nodes": {
                "model.project.orders": {
                    "name": "orders",
                    "raw_code": "select * from upstream",
                },
                "model.project.customers": {
                    "name": "customers",
                    "raw_code": "select * from raw_customers",
                },
            }
        },
        models={"orders": {"sql": "select * from upstream"}},
    )

    trimmed = pipeline._trim_redundant_context(context)

    assert "raw_code" not in trimmed.manifest["nodes"]["model.project.orders"]
    assert (
        trimmed.manifest["nodes"]["model.project.customers"]["raw_code"]
        == "select * from raw_customers"
    )


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
        if app_name == "dbt_context":
            return json.dumps(
                {
                    "diagnostic": record.diagnostic.model_dump(),
                    "manifest": {"nodes": {}, "lineage": {}},
                    "compiled_sql": {},
                    "git": {},
                    "models": {},
                    "macros": {},
                    "lineage": {},
                }
            )
        return "confidence: 0.9\nroot_cause: broken join"

    monkeypatch.setattr(pipeline, "setup_langfuse", lambda: False)
    monkeypatch.setattr(pipeline, "flush_langfuse", lambda: None)
    monkeypatch.setattr(pipeline, "is_auto_fixable", lambda diagnostic: True)
    monkeypatch.setattr(pipeline.settings, "google_api_key", "test-key")
    monkeypatch.setattr(pipeline, "_run_agent", fake_run_agent)

    result = await pipeline.run_investigation(record.incident_id)

    assert result.status == IncidentStatus.INVESTIGATED
    assert len(calls) == 2
    assert [call[1] for call in calls] == ["dbt_context", "dbt_investigation"]
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

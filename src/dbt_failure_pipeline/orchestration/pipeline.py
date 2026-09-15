"""Deterministic investigation orchestration."""

from __future__ import annotations

import asyncio
import json
import os
import re
from contextlib import nullcontext

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from dbt_failure_pipeline.agents.context import context_agent
from dbt_failure_pipeline.agents.correction import correction_agent
from dbt_failure_pipeline.agents.investigation import investigation_agent
from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.core.models import (
    ErrorCategory,
    IncidentStatus,
    InvestigationContext,
    InvestigationRecord,
    ProposedPatch,
    RootCauseAnalysis,
)
from dbt_failure_pipeline.core.state import load_incident, save_incident
from dbt_failure_pipeline.evaluation.classification import classify_diagnostic, is_auto_fixable
from dbt_failure_pipeline.observability.langfuse_setup import (
    flush_langfuse,
    setup_langfuse,
    trace_context,
)

_SOURCE_DATA_MARKERS = (
    "source data issue:",
    "source-data issue:",
    "source data correction is required",
    "source-data correction is required",
)


async def _run_agent(agent, message: str, app_name: str, session_id: str) -> str:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=app_name, user_id="dbt-failure-agent", session_id=session_id
    )
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
    user_msg = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    tool_result = ""
    async for event in runner.run_async(
        user_id="dbt-failure-agent", session_id=session_id, new_message=user_msg
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                function_response = part.function_response
                if function_response and function_response.name == "propose_patch":
                    response = function_response.response or {}
                    result = response.get("result") if isinstance(response, dict) else response
                    if result is None and isinstance(response, dict) and "diff_unified" in response:
                        result = response
                    if isinstance(result, str):
                        tool_result = result
                    elif result is not None:
                        tool_result = json.dumps(result)
        if event.is_final_response():
            if event.content and event.content.parts:
                final_text = event.content.parts[0].text or ""
            elif event.error_message:
                final_text = f"Agent error: {event.error_message}"
    return final_text if "diff_unified" in final_text else tool_result or final_text


def _parse_patch_from_output(output: str) -> ProposedPatch | None:
    try:
        if "diff_unified" in output:
            start = output.find("{")
            end = output.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(output[start:end])
                return ProposedPatch(
                    file_path=data.get("file_path", ""),
                    summary=data.get("summary", ""),
                    diff_unified=data.get("diff_unified", ""),
                    original_content=data.get("original_content", ""),
                    patched_content=data.get("patched_content", ""),
                    confidence=0.75,
                    tests_to_run=["dbt compile", "dbt test"],
                )
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:diff)?\n(.*?)```", output, re.DOTALL)
    if m:
        return ProposedPatch(
            file_path="",
            summary="Patch from agent output",
            diff_unified=m.group(1),
            confidence=0.6,
            tests_to_run=["dbt compile", "dbt test"],
        )
    return None


def _parse_context_from_output(output: str) -> InvestigationContext:
    """Parse the context agent's JSON-only response."""
    candidate = output.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate).strip()
    start = candidate.find("{")
    end = candidate.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("Context agent did not return a JSON object")
    try:
        return InvestigationContext.model_validate(json.loads(candidate[start:end]))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid context agent response: {exc}") from exc


def _build_rca_from_investigation(output: str) -> RootCauseAnalysis:
    confidence = 0.5
    conf_match = re.search(r"confidence[:\s]+([0-9.]+)", output, re.IGNORECASE)
    if conf_match:
        confidence = min(0.95, max(0.15, float(conf_match.group(1))))

    requires_human = confidence < settings.confidence_threshold or "infrastructure" in output.lower()
    return RootCauseAnalysis(
        error_type="dbt_failure",
        observations=[],
        hypotheses=[],
        root_cause=output[:500],
        confidence=confidence,
        evidence=[output[:1000]],
        requires_human_intervention=requires_human,
    )


def _is_source_data_issue(output: str) -> bool:
    """Detect an explicit source-data conclusion, not incidental mentions."""
    for line in output.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith(_SOURCE_DATA_MARKERS):
            return True
        if "conclusion:" in normalized:
            conclusion = normalized.split("conclusion:", 1)[1].strip()
            if conclusion.startswith(_SOURCE_DATA_MARKERS):
                return True
    return False


def _context_tool_policy(diagnostic) -> dict[str, object]:
    """Build a minimal, diagnostic-specific collection policy for context_agent."""
    category = classify_diagnostic(diagnostic)
    messages = " ".join(
        node.error_message or "" for node in diagnostic.failed_nodes
    ).lower()
    failed_types = {node.node_type.lower() for node in diagnostic.failed_nodes}

    sql_markers = (
        "runtime error",
        "binder error",
        "syntax error",
        "parser error",
        "catalog error",
        "compilation",
        "cast",
        "conversion",
        "invalid function",
    )
    macro_markers = ("macro", "jinja", "{{", "}}", "generate_series")
    relationship_markers = (
        "relationship",
        "referential",
        "foreign key",
        "orphan",
        "upstream",
        "downstream",
    )
    has_sql_error = category in {
        ErrorCategory.SQL_COMPILATION,
        ErrorCategory.DATA_ERROR,
    } or any(marker in messages for marker in sql_markers)
    has_macro_signal = any(marker in messages for marker in macro_markers)
    has_lineage_signal = (
        category
        in {
            ErrorCategory.SCHEMA_CHANGE,
            ErrorCategory.DEPENDENCY_ERROR,
        }
        or any(marker in messages for marker in relationship_markers)
    )
    is_test = (
        category == ErrorCategory.DBT_TEST_FAILURE
        or "test" in failed_types
    )

    required: list[str] = []
    optional: dict[str, str] = {}
    forbidden: list[str] = ["get_dbt_diagnostic"]

    if is_test:
        if any(marker in messages for marker in relationship_markers):
            required.append("get_dbt_manifest")
        else:
            optional["get_dbt_manifest"] = (
                "only if lineage is needed to identify the tested relation"
            )
        optional["get_dbt_models"] = (
            "only for the failed model or the model producing the tested relation"
        )
        forbidden.extend(["get_dbt_compiled_sql", "get_dbt_macros"])
    else:
        if has_lineage_signal or category == ErrorCategory.UNKNOWN:
            required.append("get_dbt_manifest")
        if has_sql_error:
            required.append("get_dbt_compiled_sql")
        if category in {
            ErrorCategory.SCHEMA_CHANGE,
            ErrorCategory.DEPENDENCY_ERROR,
        } or "regression" in messages:
            required.append("get_dbt_git_history")
        if has_lineage_signal or has_sql_error or category == ErrorCategory.UNKNOWN:
            required.append("get_dbt_models")

        if has_macro_signal:
            required.append("get_dbt_macros")
        else:
            forbidden.append("get_dbt_macros")

        if "get_dbt_manifest" not in required and has_sql_error:
            optional["get_dbt_manifest"] = (
                "only if source SQL alone cannot identify the referenced relation"
            )
        if "get_dbt_git_history" not in required:
            optional["get_dbt_git_history"] = (
                "only if the collected evidence suggests a recent regression"
            )

    return {
        "error_category": category.value,
        "required": list(dict.fromkeys(required)),
        "optional": optional,
        "forbidden": list(dict.fromkeys(forbidden)),
        "selection_constraints": [
            "Use failed node IDs for artifact tools.",
            (
                "Call get_dbt_models only after get_dbt_manifest when model "
                "selection depends on lineage."
            ),
            (
                "Request the failed model and only upstream models that determine "
                "the failing expression; exclude downstream models unless their "
                "impact is explicitly needed."
            ),
            "Never request an unscoped macro inventory.",
        ],
    }


def _trim_redundant_context(context: InvestigationContext) -> InvestigationContext:
    """Remove manifest SQL duplicated by the targeted models evidence."""
    compact = context.model_copy(deep=True)
    model_names = set(compact.models)
    for node in compact.manifest.get("nodes", {}).values():
        if node.get("name") in model_names:
            node.pop("raw_code", None)
    return compact


async def run_investigation(incident_id: str) -> InvestigationRecord:
    langfuse_enabled = setup_langfuse()
    record = load_incident(incident_id)
    record.status = IncidentStatus.INVESTIGATING
    save_incident(record)

    diagnostic = record.diagnostic
    record.diagnostic = diagnostic

    if not is_auto_fixable(diagnostic):
        record.status = IncidentStatus.NEEDS_HUMAN
        save_incident(record)
        flush_langfuse()
        return record

    if not settings.google_api_key:
        record.status = IncidentStatus.NEEDS_HUMAN
        save_incident(record)
        flush_langfuse()
        return record

    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)

    primary = diagnostic.primary_failed_node
    trace_ctx = (
        trace_context(
            incident_id=incident_id,
            scenario_id=record.scenario_id,
            error_category=classify_diagnostic(diagnostic).value,
            model_name=primary.node_name if primary else "unknown",
        )
        if langfuse_enabled
        else nullcontext()
    )

    with trace_ctx:
        failed_ids = ",".join(node.unique_id for node in diagnostic.failed_nodes)
        context_prompt = f"""Build the investigation context for incident {incident_id}.

Failed node IDs: {failed_ids}

The diagnostic currently associated with the incident is:
{diagnostic.model_dump_json(indent=2)}

Collection policy derived from the diagnostic:
{json.dumps(_context_tool_policy(diagnostic), indent=2)}

Use only the tools justified by this policy and explain each selected tool in
tool_reasons.
Return only the validated InvestigationContext JSON and list the tools actually
called in sources_used.
"""
        try:
            context_output = await _run_agent(
                context_agent,
                context_prompt,
                "dbt_context",
                f"context-{incident_id}",
            )
            context = _parse_context_from_output(context_output)
            context = _trim_redundant_context(context)
        except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            record.metadata["context_error"] = str(exc)
            record.status = IncidentStatus.NEEDS_HUMAN
            save_incident(record)
            flush_langfuse()
            return record

        record.metadata["lineage"] = context.lineage
        record.metadata["context_sources_used"] = context.sources_used
        record.metadata["context_tool_reasons"] = context.tool_reasons
        inv_prompt = f"""Investigate the dbt root cause using only this deterministic context.

{context.model_dump_json(indent=2)}

Provide observations, hypotheses, root cause, confidence, affected models, and evidence.
Do not propose a patch.
"""
        record.investigation_output = await _run_agent(
            investigation_agent, inv_prompt, "dbt_investigation", f"inv-{incident_id}"
        )
        record.rca = _build_rca_from_investigation(record.investigation_output)
        record.failures = []
        for node in diagnostic.failed_nodes:
            failure_rca = record.rca.model_dump()
            failure_rca["error_type"] = classify_diagnostic(diagnostic).value
            failure_rca["affected_models"] = [node.unique_id]
            record.failures.append(RootCauseAnalysis(**failure_rca))

    if _is_source_data_issue(record.investigation_output):
        record.rca.requires_human_intervention = True
        record.metadata["source_data_issue"] = True
        record.correction_output = (
            "Source data issue: source records or relationships are inconsistent. "
            "No dbt model modification is justified by the available evidence; "
            "source-data correction or human/business review is required."
        )
        record.status = IncidentStatus.NEEDS_HUMAN
    else:
        record.status = IncidentStatus.INVESTIGATED
    save_incident(record)
    flush_langfuse()
    return record


async def run_correction(incident_id: str) -> InvestigationRecord:
    """Ask the correction agent for a patch after investigation is reviewed."""
    record = load_incident(incident_id)
    if record.metadata.get("source_data_issue"):
        record.status = IncidentStatus.NEEDS_HUMAN
        record.correction_output = (
            "Source data issue: no model patch will be proposed. "
            "Source-data correction or human/business review is required."
        )
        save_incident(record)
        return record
    if not record.rca or record.status != IncidentStatus.INVESTIGATED:
        record.status = IncidentStatus.NEEDS_HUMAN
        save_incident(record)
        return record

    if not settings.google_api_key:
        record.status = IncidentStatus.NEEDS_HUMAN
        save_incident(record)
        return record

    os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
    corr_prompt = f"""Propose a minimal fix for ONE file.

Diagnostic:
{record.diagnostic.model_dump_json(indent=2)}

Investigation:
{record.investigation_output}

Use propose_patch with the full corrected SQL content.
Return only the concise fix proposal and the structured patch result.
Do not repeat the root cause, explanation, evidence, confidence, or test list.
"""
    record.correction_output = await _run_agent(
        correction_agent, corr_prompt, "dbt_correction", f"corr-{incident_id}"
    )
    record.patch = _parse_patch_from_output(record.correction_output)
    record.patches = [record.patch] if record.patch else []
    record.status = (
        IncidentStatus.AWAITING_APPROVAL if record.patch else IncidentStatus.NEEDS_HUMAN
    )
    save_incident(record)
    flush_langfuse()
    return record


def main() -> None:
    from dbt_failure_pipeline.core.state import get_current_incident_id

    incident_id = get_current_incident_id()
    if not incident_id:
        print("No current incident. Run activate_scenario.py first.")
        return
    record = asyncio.run(run_investigation(incident_id))
    print(json.dumps(record.model_dump(), indent=2, default=str))


if __name__ == "__main__":
    main()

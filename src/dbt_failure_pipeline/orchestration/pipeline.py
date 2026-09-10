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

from dbt_failure_pipeline.agents.correction import correction_agent
from dbt_failure_pipeline.agents.investigation import investigation_agent
from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.core.models import (
    IncidentStatus,
    InvestigationRecord,
    ProposedPatch,
    RootCauseAnalysis,
)
from dbt_failure_pipeline.core.state import load_incident, save_incident
from dbt_failure_pipeline.deterministic import run_diagnostic
from dbt_failure_pipeline.deterministic.investigation.context import build_investigation_context
from dbt_failure_pipeline.evaluation.classification import classify_diagnostic, is_auto_fixable
from dbt_failure_pipeline.observability.langfuse_setup import (
    flush_langfuse,
    setup_langfuse,
    trace_context,
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


async def run_investigation(incident_id: str) -> InvestigationRecord:
    langfuse_enabled = setup_langfuse()
    record = load_incident(incident_id)
    record.status = IncidentStatus.INVESTIGATING
    save_incident(record)

    diagnostic = run_diagnostic()
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

    try:
        context = build_investigation_context()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        record.metadata["context_error"] = str(exc)
        record.status = IncidentStatus.NEEDS_HUMAN
        save_incident(record)
        flush_langfuse()
        return record

    record.metadata["lineage"] = context.lineage
    with trace_ctx:
        inv_prompt = f"""Investigate the dbt root cause using only this deterministic context.

{context.model_dump_json(indent=2)}

Provide observations, hypotheses, root cause, confidence, affected models, and evidence.
Do not propose a patch.
"""
        record.investigation_output = await _run_agent(
            investigation_agent, inv_prompt, "dbt_investigation", f"inv-{incident_id}"
        )
        record.rca = _build_rca_from_investigation(record.investigation_output)

    record.status = IncidentStatus.INVESTIGATED
    save_incident(record)
    flush_langfuse()
    return record


async def run_correction(incident_id: str) -> InvestigationRecord:
    """Ask the correction agent for a patch after investigation is reviewed."""
    record = load_incident(incident_id)
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

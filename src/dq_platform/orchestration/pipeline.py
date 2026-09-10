"""Deterministic orchestration pipeline for DQ investigation."""

from __future__ import annotations

import asyncio
import json
import uuid

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from dq_platform.agents.correction import correction_agent
from dq_platform.agents.investigation import investigation_agent
from dq_platform.config import settings
from dq_platform.models import AnomalyEvent
from dq_platform.observability.langfuse_setup import setup_langfuse
from dq_platform.quality.runner import run_sql_checks


async def _run_agent(agent, message: str, app_name: str, session_id: str) -> str:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=app_name, user_id="dq-system", session_id=session_id
    )
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
    user_msg = types.Content(role="user", parts=[types.Part(text=message)])

    final_text = ""
    async for event in runner.run_async(
        user_id="dq-system", session_id=session_id, new_message=user_msg
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_text = event.content.parts[0].text or ""
            elif event.error_message:
                final_text = f"Agent error: {event.error_message}"
    return final_text


async def investigate_anomaly(event: AnomalyEvent) -> dict:
    """Run investigation + correction for a single anomaly."""
    setup_langfuse()
    inv_id = f"INV-{uuid.uuid4().hex[:8].upper()}"

    inv_prompt = f"""Investigate this data quality anomaly:

{event.model_dump_json(indent=2)}

Provide: root cause, affected tables/columns, period, business impact, evidence, and confidence (0-1).
"""
    inv_result = await _run_agent(
        investigation_agent,
        inv_prompt,
        "dq_investigation",
        f"inv-{event.anomaly_id}",
    )

    corr_prompt = f"""Based on this investigation, propose a fix:

Anomaly: {event.model_dump_json()}
Investigation result: {inv_result}

Use propose_patch if a dbt model change is needed.
"""
    corr_result = await _run_agent(
        correction_agent,
        corr_prompt,
        "dq_correction",
        f"corr-{event.anomaly_id}",
    )

    return {
        "investigation_id": inv_id,
        "anomaly_id": event.anomaly_id,
        "investigation_result": inv_result,
        "correction_result": corr_result,
    }


async def run_pipeline() -> list[dict]:
    """Full pipeline: detect -> investigate -> propose correction."""
    anomalies = run_sql_checks()
    if not anomalies:
        print("No anomalies detected.")
        return []

    if not settings.google_api_key:
        print("GOOGLE_API_KEY not set — skipping agent investigation.")
        return anomalies

    results = []
    for a in anomalies[:3]:
        event = AnomalyEvent(
            anomaly_id=a["anomaly_id"],
            table=a.get("table", "raw_orders"),
            metric=a.get("metric", a["anomaly_type"]),
            observed_value=a["observed_value"],
            expected_value=a.get("expected_value"),
            deviation=a.get("deviation"),
            date=a["date"],
        )
        print(f"Investigating {event.anomaly_id}...")
        result = await investigate_anomaly(event)
        results.append(result)
        print(f"  Investigation complete: {result['investigation_id']}")

    return results


def main() -> None:
    results = asyncio.run(run_pipeline())
    print(json.dumps(results, indent=2, default=str))

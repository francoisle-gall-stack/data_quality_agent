"""Conversation orchestration for the dashboard."""

from __future__ import annotations

import json
import uuid

from dq_platform.agents.business_qa import business_qa_agent
from dq_platform.config import settings
from dq_platform.orchestration.intent_router import classify_intent
from dq_platform.orchestration.agent_runner import run_agent
from dbt_failure_pipeline.agents.context import create_business_context_agent


async def answer_question(question: str, dashboard_context: dict) -> str:
    intent = classify_intent(question, dashboard_context.get("chart_id"))
    if not settings.google_api_key:
        return "L'agent conversationnel est désactivé : GOOGLE_API_KEY n'est pas configurée."
    request = {
        "question": question,
        "intent": intent.name,
        "collection_policy": intent.tools,
        "dashboard_context": dashboard_context,
    }
    context_output = await run_agent(
        create_business_context_agent(),
        json.dumps(request, ensure_ascii=False),
        "dq_business_context",
        f"context-{uuid.uuid4().hex[:8]}",
    )
    qa_prompt = json.dumps(
        {"question": question, "intent": intent.name, "dashboard_context": dashboard_context, "evidence": context_output},
        ensure_ascii=False,
    )
    return await run_agent(business_qa_agent, qa_prompt, "dq_business_qa", f"qa-{uuid.uuid4().hex[:8]}")

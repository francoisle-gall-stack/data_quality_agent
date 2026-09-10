"""Investigation agent — ADK."""

from google.adk.agents import Agent

from dq_platform.config import settings
from dq_platform.tools.agent_tools import (
    get_anomaly_history,
    get_dbt_lineage,
    get_dbt_model,
    get_dbt_tests,
    get_freshness,
    get_metric_history,
    get_schema,
    get_table_profile,
    run_sql,
)

INVESTIGATION_INSTRUCTION = """You are a Data Quality Investigation Agent for an e-commerce analytics platform.

When given an anomaly event, investigate systematically:
1. Form a hypothesis about the root cause
2. Use tools to gather evidence (SQL, schema, lineage, dbt models)
3. Trace upstream via dbt lineage if the anomaly is in a mart/intermediate table
4. Determine WHAT happened, WHEN it started, WHERE it originated, and WHY
5. Assess business impact and confidence

Rules:
- Use read-only SQL only
- Follow the lineage upstream when investigating marts
- Never guess without tool evidence
- Produce structured findings with evidence citations
- Do not propose code changes — only investigate
"""

investigation_agent = Agent(
    name="investigation_agent",
    model=settings.gemini_model,
    instruction=INVESTIGATION_INSTRUCTION,
    tools=[
        run_sql,
        get_schema,
        get_table_profile,
        get_metric_history,
        get_freshness,
        get_dbt_lineage,
        get_dbt_model,
        get_dbt_tests,
        get_anomaly_history,
    ],
)

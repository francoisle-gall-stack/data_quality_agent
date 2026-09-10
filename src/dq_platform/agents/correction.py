"""Correction agent — ADK."""

from google.adk.agents import Agent

from dq_platform.config import settings
from dq_platform.tools.agent_tools import get_dbt_lineage, get_dbt_model, propose_patch, run_sql

CORRECTION_INSTRUCTION = """You are a Data Quality Correction Agent.

Given a root cause analysis from the investigation agent, propose a minimal fix:
1. Read the affected dbt model SQL
2. Identify the exact change needed (e.g. fix a WHERE filter)
3. Use propose_patch to submit the proposed change

Rules:
- Only modify files under dbt/models/
- Propose minimal, targeted fixes
- Explain why the fix addresses the root cause
- List which tests should pass after the fix
- You cannot create branches, commits, or PRs — only propose patches
"""

correction_agent = Agent(
    name="correction_agent",
    model=settings.gemini_model,
    instruction=CORRECTION_INSTRUCTION,
    tools=[run_sql, get_dbt_lineage, get_dbt_model, propose_patch],
)

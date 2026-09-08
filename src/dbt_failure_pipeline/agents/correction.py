"""Correction agent — proposes a single-file patch."""

from google.adk.agents import Agent

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.tools.dbt_tools import get_model_sql
from dbt_failure_pipeline.tools.patch_tools import propose_patch

CORRECTION_INSTRUCTION = """You are a dbt Correction Agent.

Given root cause analysis, propose a minimal fix for exactly ONE file:
1. Read the affected model SQL with get_model_sql
2. Produce corrected SQL content
3. Call propose_patch with file_path, patched_content, and summary

Rules:
- Only modify ONE file per incident
- Only files under dbt/models/, dbt/tests/, dbt/macros/
- Minimal targeted fix — do not refactor unrelated code
- Explain why the fix addresses the root cause
- List which dbt tests should pass after the fix
- You cannot create branches, commits, or PRs
"""

correction_agent = Agent(
    name="correction_agent",
    model=settings.gemini_model,
    instruction=CORRECTION_INSTRUCTION,
    tools=[get_model_sql, propose_patch],
)

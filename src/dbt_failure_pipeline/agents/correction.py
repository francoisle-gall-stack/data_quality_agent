"""Correction agent — proposes a single-file patch."""

from google.adk.agents import Agent

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.tools.model_tools import get_dbt_model
from dbt_failure_pipeline.tools.patch_tools import propose_patch

CORRECTION_INSTRUCTION = """You are a dbt Correction Agent.

Given the diagnostic and investigation, propose a minimal fix for exactly ONE file.
First call get_dbt_model with the affected model name to retrieve its current dbt
source SQL. Preserve its Jinja, ref(), source(), and config expressions. Then call
propose_patch with file_path, the complete corrected source SQL, and summary.

Rules:
- Only modify ONE file per incident
- Only files under dbt/models/, dbt/tests/, dbt/macros/
- Minimal targeted fix — do not refactor unrelated code
- You cannot create branches, commits, or PRs

Output only:
- A concise fix proposal
- The complete corrected SQL

Do not repeat the root cause or provide a separate explanation, evidence, confidence,
or test list. Always use propose_patch to return the structured patch.
"""

correction_agent = Agent(
    name="correction_agent",
    model=settings.gemini_model,
    instruction=CORRECTION_INSTRUCTION,
    tools=[get_dbt_model, propose_patch],
)

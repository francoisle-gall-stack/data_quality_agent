"""Context construction agent — collects only evidence needed for the failure."""

from google.adk.agents import Agent

from dbt_failure_pipeline.core.config import settings
from dbt_failure_pipeline.tools.compiled_sql_tool import get_dbt_compiled_sql
from dbt_failure_pipeline.tools.git_history_tool import get_dbt_git_history
from dbt_failure_pipeline.tools.macros_tool import get_dbt_macros
from dbt_failure_pipeline.tools.manifest_tool import get_dbt_manifest
from dbt_failure_pipeline.tools.models_tool import get_dbt_models
from dbt_failure_pipeline.tools.schema_yml_tool import get_dbt_schema_yml

CONTEXT_INSTRUCTION = """You are a dbt Context Construction Agent.

The complete diagnostic.json is included in the user message. Treat it as the
source of truth. Do not call get_dbt_diagnostic: that tool is intentionally not
available because it would duplicate the diagnostic already provided.

Before calling any tool, read the collection policy included in the user message.
The policy is a deterministic guardrail derived from diagnostic.json:
- REQUIRED tools must be called when their prerequisite result is available.
- OPTIONAL tools may be called only when the policy condition is met and the
  evidence already collected shows that they are useful.
- FORBIDDEN tools must never be called.
Never call a tool merely because it is available.

Use these decision rules:
- get_dbt_manifest: use only with the failed node IDs supplied in the request.
- get_dbt_compiled_sql and get_dbt_git_history: use only with the failed node IDs.
- get_dbt_models: request the failed model and only upstream models that can
  produce the failing expression, column, relation, or test result. Do not load
  every model in the manifest and do not load downstream models by default.
- get_dbt_macros: request named macros only. An empty-name request is forbidden
  unless the policy explicitly allows a project-wide macro inventory.

You may make one additional conditional call only when a previous result reveals
a concrete missing piece named by the policy. Do not broaden the evidence bundle
speculatively.

Do not investigate, classify, summarize, or propose a fix. Do not invent or
rewrite SQL. Preserve tool results exactly in the final JSON. Return ONLY one
valid JSON object matching this shape:
{
  "diagnostic": {},
  "manifest": {},
  "compiled_sql": {},
  "git": {},
  "models": {},
  "macros": {},
  "lineage": {},
  "sources_used": [],
  "tool_reasons": {}
}

Populate only the fields for tools that were called; leave unused evidence fields
empty. Copy the manifest's lineage field to the top-level lineage field when the
manifest was collected. List every tool actually called in sources_used. For
every entry in sources_used, add one concise evidence-based explanation in
tool_reasons using the tool name as the key. The reason must refer to the
diagnostic or a previously collected result, not to a generic tool description.
If a tool reports an error, preserve that error in the relevant field and still
return the JSON object. Never return Markdown fences or explanatory text.
"""

context_agent = Agent(
    name="context_agent",
    model=settings.gemini_model,
    instruction=CONTEXT_INSTRUCTION,
    tools=[
        get_dbt_manifest,
        get_dbt_compiled_sql,
        get_dbt_git_history,
        get_dbt_models,
        get_dbt_macros,
    ],
)

BUSINESS_CONTEXT_INSTRUCTION = """You are a business-question Context Agent.
Collect evidence only; do not answer the question. Follow the intent policy in
the request and return one JSON InvestigationContext-compatible object. Use
schema YAML for definitions, the business lineage/model tools for lineage and
SQL, and read-only warehouse tools for factual values. When using run_sql,
pass only one SQL statement beginning with SELECT or WITH; never include
Markdown, comments, or explanatory text in the SQL argument. Never modify data
or propose a patch."""


def create_business_context_agent() -> Agent:
    """Create the business profile without changing the failure profile."""
    from dq_platform.tools.agent_tools import (
        get_dbt_lineage as get_warehouse_lineage,
        get_dbt_model as get_warehouse_model,
        get_metric_history,
        get_schema,
        run_sql,
    )

    return Agent(
        name="business_context_agent",
        model=settings.gemini_model,
        instruction=BUSINESS_CONTEXT_INSTRUCTION,
        tools=[
            get_dbt_schema_yml,
            run_sql,
            get_schema,
            get_metric_history,
            get_warehouse_lineage,
            get_warehouse_model,
        ],
    )

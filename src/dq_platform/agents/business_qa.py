"""Tool-less agent that answers from a collected evidence bundle."""

from google.adk.agents import Agent

from dq_platform.config import settings

BUSINESS_QA_INSTRUCTION = """You answer business users in French using only the
evidence bundle in the request. Be concise and explicit. Cite the exact dbt
model, YAML description, table, and lineage used. If evidence is missing, say
so instead of guessing. Never propose code changes. Format with Réponse,
Sources utilisées, and Lineage when relevant."""

business_qa_agent = Agent(
    name="business_qa_agent",
    model=settings.gemini_model,
    instruction=BUSINESS_QA_INSTRUCTION,
)

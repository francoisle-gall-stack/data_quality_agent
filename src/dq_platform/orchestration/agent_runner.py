"""Shared ADK runner for conversational agents."""

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


async def run_agent(agent, message: str, app_name: str, session_id: str) -> str:
    """Run an agent for one request and return its final response."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=app_name,
        user_id="dq-dashboard",
        session_id=session_id,
    )
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
    user_msg = types.Content(role="user", parts=[types.Part(text=message)])

    final_text = ""
    async for event in runner.run_async(
        user_id="dq-dashboard",
        session_id=session_id,
        new_message=user_msg,
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_text = event.content.parts[0].text or ""
            elif event.error_message:
                final_text = f"Agent error: {event.error_message}"
    return final_text

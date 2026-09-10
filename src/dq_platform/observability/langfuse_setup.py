"""Langfuse observability setup for ADK agents."""

from __future__ import annotations

import os

from dq_platform.config import settings


def setup_langfuse() -> bool:
    """Initialize Langfuse OTel instrumentation for Google ADK."""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return False

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_BASE_URL", settings.langfuse_base_url)

    try:
        from openinference.instrumentation.google_adk import GoogleADKInstrumentor

        GoogleADKInstrumentor().instrument()
        return True
    except Exception:
        return False

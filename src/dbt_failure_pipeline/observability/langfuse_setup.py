"""Langfuse observability for ADK agents."""

from __future__ import annotations

import logging
import os
from contextlib import AbstractContextManager, ExitStack, nullcontext
from typing import Any

from dbt_failure_pipeline.core.config import settings

logger = logging.getLogger(__name__)

_langfuse_client: Any = None
_instrumented = False


def _export_credentials_to_environ() -> str:
    """Mirror Pydantic settings into os.environ for Langfuse SDK / OTEL."""
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    base_url = settings.langfuse_base_url or os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    os.environ.setdefault("LANGFUSE_BASE_URL", base_url)
    os.environ.setdefault("LANGFUSE_HOST", base_url)
    return base_url


def setup_langfuse() -> bool:
    """Initialize Langfuse OTEL exporter, then instrument Google ADK."""
    global _langfuse_client, _instrumented

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        logger.info("Langfuse keys not configured — tracing disabled.")
        return False

    base_url = _export_credentials_to_environ()

    try:
        from langfuse import Langfuse
        from openinference.instrumentation.google_adk import GoogleADKInstrumentor
        from opentelemetry import trace as otel_trace

        # Langfuse v4 (events_only) requires the ingestion header for OTLP spans to appear in the UI.
        v4_headers = {"x-langfuse-ingestion-version": "4"}

        # Langfuse must register the TracerProvider + OTLP exporter BEFORE ADK instrumentation.
        _langfuse_client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=base_url,
            additional_headers=v4_headers,
        )
        try:
            auth_ok = bool(_langfuse_client.auth_check())
        except Exception as exc:
            logger.warning("Langfuse auth_check failed: %s", exc)
            return False

        if not auth_ok:
            logger.warning("Langfuse auth_check failed — verify LANGFUSE_BASE_URL and API keys.")
            return False

        if not _instrumented:
            tracer_provider = otel_trace.get_tracer_provider()
            GoogleADKInstrumentor().instrument(tracer_provider=tracer_provider)
            _instrumented = True
            logger.info("Langfuse + Google ADK instrumentation enabled (v4 ingestion).")

        return True
    except ImportError:
        logger.warning("Langfuse or openinference-google-adk not installed — tracing disabled.")
        return False
    except Exception as exc:
        logger.warning("Langfuse setup failed: %s", exc)
        return False


class _InvestigationTraceContext(AbstractContextManager[Any]):
    """Root Langfuse agent observation + propagated session/tags for ADK child spans."""

    def __init__(
        self,
        *,
        incident_id: str,
        scenario_id: str | None,
        error_category: str,
        model_name: str,
    ) -> None:
        self._incident_id = incident_id
        self._scenario_id = scenario_id
        self._error_category = error_category
        self._model_name = model_name
        self._stack: ExitStack | None = None
        self._root: Any = None

    def __enter__(self) -> Any:
        from langfuse import propagate_attributes

        trace_name = f"dbt-investigation-{self._incident_id}"
        metadata = {
            "incident_id": self._incident_id,
            "scenario_id": self._scenario_id,
            "error_category": self._error_category,
            "model_name": self._model_name,
        }
        tags = [t for t in [self._scenario_id, self._error_category, self._model_name] if t]

        self._stack = ExitStack()
        self._stack.__enter__()
        self._root = self._stack.enter_context(
            _langfuse_client.start_as_current_observation(
                name=trace_name,
                as_type="agent",
                metadata=metadata,
            )
        )
        self._stack.enter_context(
            propagate_attributes(
                session_id=self._incident_id,
                trace_name=trace_name,
                tags=tags,
                metadata=metadata,
            )
        )
        return self._root

    def __exit__(self, exc_type, exc, tb) -> bool | None:
        if self._stack is not None:
            return self._stack.__exit__(exc_type, exc, tb)
        return None


def trace_context(
    *,
    incident_id: str,
    scenario_id: str | None,
    error_category: str,
    model_name: str,
) -> AbstractContextManager[Any]:
    """Return a Langfuse trace context manager grouping all agent spans per incident."""
    if _langfuse_client is None:
        return nullcontext()

    try:
        return _InvestigationTraceContext(
            incident_id=incident_id,
            scenario_id=scenario_id,
            error_category=error_category,
            model_name=model_name,
        )
    except Exception as exc:
        logger.warning("Could not create Langfuse trace context: %s", exc)
        return nullcontext()


def flush_langfuse() -> None:
    """Flush pending OTEL spans to Langfuse."""
    if _langfuse_client is not None:
        try:
            _langfuse_client.flush()
        except Exception as exc:
            logger.warning("Langfuse flush failed: %s", exc)

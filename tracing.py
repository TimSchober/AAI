"""
Optional tracing support for the AAI project using Phoenix/OpenTelemetry.

The module initializes tracing automatically when the required packages are
available and tracing is enabled. If Phoenix is not installed or disabled,
the helpers fall back to no-op implementations so the app can still run.
"""

from __future__ import annotations

import inspect
import os
from contextlib import contextmanager
from functools import wraps
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.trace import Span, Tracer

try:  # pragma: no cover - optional dependency
    import phoenix as px
except Exception:  # pragma: no cover - optional dependency
    px = None

try:  # pragma: no cover - optional dependency
    from phoenix.otel import register as register_phoenix
except Exception:  # pragma: no cover - optional dependency
    register_phoenix = None

try:  # pragma: no cover - optional dependency
    from openinference.instrumentation.openai import OpenAIInstrumentor
except Exception:  # pragma: no cover - optional dependency
    OpenAIInstrumentor = None

_TRACER: Tracer | None = None
_TRACE_INITIALIZED = False


def _is_tracing_enabled() -> bool:
    value = os.getenv("AAI_TRACING_ENABLED", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _get_project_name() -> str:
    return os.getenv("PHOENIX_PROJECT_NAME", "aai-job-search")


def init_tracing(project_name: str | None = None, launch_ui: bool = False) -> Tracer:
    """Initialize Phoenix tracing if available and return a tracer."""
    global _TRACER, _TRACE_INITIALIZED

    if _TRACE_INITIALIZED and _TRACER is not None:
        return _TRACER

    if not _is_tracing_enabled():
        _TRACER = trace.get_tracer("aai_app")
        _TRACE_INITIALIZED = False
        return _TRACER

    if px is None or register_phoenix is None:
        _TRACER = trace.get_tracer("aai_app")
        _TRACE_INITIALIZED = False
        return _TRACER

    try:
        if launch_ui:
            px.launch_app()

        provider = register_phoenix(project_name=project_name or _get_project_name())
        if OpenAIInstrumentor is not None:
            OpenAIInstrumentor().instrument(tracer_provider=provider)

        _TRACER = trace.get_tracer("aai_app")
        _TRACE_INITIALIZED = True
        return _TRACER
    except Exception:  # pragma: no cover - defensive fallback
        _TRACER = trace.get_tracer("aai_app")
        _TRACE_INITIALIZED = False
        return _TRACER


def get_tracer() -> Tracer:
    if _TRACER is None:
        return init_tracing()
    return _TRACER


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Span]:
    """Create a tracing span with optional attributes."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as current_span:
        for key, value in attributes.items():
            if isinstance(value, (str, int, float, bool)):
                current_span.set_attribute(key, value)
            else:
                current_span.set_attribute(key, str(value))
        yield current_span


def traced(name: str | None = None):
    """Decorator that wraps a function or coroutine in a tracing span."""

    def decorator(func):
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with span(name or func.__name__):
                    return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with span(name or func.__name__):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator

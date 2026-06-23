"""Thin OpenTelemetry -> Phoenix (ai-stack :4317) wiring.

Not full observability (that is Phase 6) - just enough trace discipline from day one
(doc 07 §5.9: don't enable Phoenix only after things break). Each chat turn opens a span
and its trace_id is stored on model_runs/messages. If no OTLP endpoint is configured,
tracing degrades to a no-op and the rest of Core is unaffected.
"""

from __future__ import annotations

from hibob_core.config import settings

_tracer = None


def init_tracing() -> None:
    global _tracer
    if not settings.otlp_endpoint:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.service_name})
        )
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True))
        )
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("hibob.core")
    except Exception:  # tracing must never break the request path
        _tracer = None


def start_chat_span(conversation_id: str):
    """Context manager yielding a trace_id string (or a no-op span)."""
    if _tracer is None:
        return _NoopSpan()
    return _ChatSpan(_tracer, conversation_id)


class _NoopSpan:
    trace_id = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _ChatSpan:
    def __init__(self, tracer, conversation_id: str):
        self._cm = tracer.start_as_current_span("chat.turn")
        self._conversation_id = conversation_id
        self.trace_id: str | None = None

    def __enter__(self):
        self._span = self._cm.__enter__()
        self._span.set_attribute("conversation.id", self._conversation_id)
        ctx = self._span.get_span_context()
        self.trace_id = format(ctx.trace_id, "032x")
        return self

    def __exit__(self, *a):
        return self._cm.__exit__(*a)

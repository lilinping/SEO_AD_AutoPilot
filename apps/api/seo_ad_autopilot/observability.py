from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Optional

from .config import Settings, get_settings

try:  # pragma: no cover - optional dependency
    import sentry_sdk
except Exception:  # pragma: no cover - optional dependency
    sentry_sdk = None

try:  # pragma: no cover - optional dependency
    from opentelemetry import trace as otel_trace
except Exception:  # pragma: no cover - optional dependency
    otel_trace = None

try:  # pragma: no cover - optional dependency
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
except Exception:  # pragma: no cover - optional dependency
    TracerProvider = None
    BatchSpanProcessor = None
    SimpleSpanProcessor = None
    InMemorySpanExporter = None

try:  # pragma: no cover - optional dependency
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except Exception:  # pragma: no cover - optional dependency
    OTLPSpanExporter = None

_tracer = None
_tracing_backend = "disabled"


def _parse_otlp_headers(raw_headers: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for part in str(raw_headers or "").split(","):
        key, sep, value = part.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


def initialize_observability(settings: Optional[Settings] = None) -> None:
    global _tracer, _tracing_backend
    settings = settings or get_settings()
    _tracing_backend = "disabled"

    if settings.sentry_dsn and sentry_sdk is not None:
        try:
            sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=1.0)
        except Exception:
            if settings.observability_strict:
                raise
    elif settings.sentry_dsn and settings.observability_strict:
        raise RuntimeError("Sentry DSN is configured but sentry_sdk is unavailable")

    if (
        not settings.enable_otlp
        or otel_trace is None
        or TracerProvider is None
        or SimpleSpanProcessor is None
        or InMemorySpanExporter is None
    ):
        if settings.enable_otlp and settings.observability_strict:
            raise RuntimeError("OTLP tracing is enabled but OpenTelemetry SDK dependencies are unavailable")
        _tracer = None
        return

    provider = TracerProvider()
    endpoint = str(settings.otlp_endpoint or "").strip()
    if endpoint:
        if OTLPSpanExporter is None or BatchSpanProcessor is None:
            if settings.observability_strict:
                raise RuntimeError("OTLP endpoint is configured but OTLP exporter dependencies are unavailable")
            provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))
            _tracing_backend = "in-memory"
        else:
            otlp_exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=_parse_otlp_headers(settings.otlp_headers),
                timeout=max(1, int(settings.otlp_timeout_ms)) / 1000.0,
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            _tracing_backend = "otlp"
    else:
        provider.add_span_processor(SimpleSpanProcessor(InMemorySpanExporter()))
        _tracing_backend = "in-memory"
    otel_trace.set_tracer_provider(provider)
    _tracer = otel_trace.get_tracer("seo-ad-autopilot")


def get_tracing_backend() -> str:
    return str(_tracing_backend or "disabled")


@contextmanager
def trace_span(name: str, attributes: Optional[dict[str, Any]] = None) -> Iterator[None]:
    if _tracer is None:
        yield
        return
    with _tracer.start_as_current_span(name) as span:  # type: ignore[union-attr]
        for key, value in (attributes or {}).items():
            try:
                span.set_attribute(str(key), value)
            except Exception:
                continue
        yield


def set_span_attributes(attributes: Optional[dict[str, Any]] = None) -> None:
    if otel_trace is None:
        return
    try:
        span = otel_trace.get_current_span()
    except Exception:
        return
    if span is None:
        return
    for key, value in (attributes or {}).items():
        try:
            span.set_attribute(str(key), value)
        except Exception:
            continue


def add_span_event(name: str, attributes: Optional[dict[str, Any]] = None) -> None:
    if otel_trace is None:
        return
    try:
        span = otel_trace.get_current_span()
    except Exception:
        return
    if span is None:
        return
    try:
        span.add_event(name, attributes or {})
    except Exception:
        return


def capture_exception(exc: Exception, *, tags: Optional[dict[str, Any]] = None) -> None:
    add_span_event("exception", {"error.type": exc.__class__.__name__, "error.message": str(exc), **{str(k): str(v) for k, v in (tags or {}).items()}})
    if sentry_sdk is not None and get_settings().sentry_dsn:
        try:
            with sentry_sdk.push_scope() as scope:
                for key, value in (tags or {}).items():
                    scope.set_tag(str(key), str(value))
                sentry_sdk.capture_exception(exc)
        except Exception:
            pass

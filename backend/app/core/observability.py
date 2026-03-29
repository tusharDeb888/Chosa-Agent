"""
Observability — OpenTelemetry setup, structured logging, and trace helpers.

Required context keys per PRD §14:
  trace_id, workflow_id, signal_id, user_id, tenant_id, ticker, agent_state
"""

from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable

import structlog
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# ────────────────────────── Structured Logging ──────────────────────────


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structlog with required context keys."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "alpha-hunter", **initial_context: Any) -> structlog.BoundLogger:
    """Get a structured logger with initial context bindings."""
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


# ────────────────────────── OpenTelemetry Tracing ──────────────────────────


_tracer_provider: TracerProvider | None = None
_meter_provider: MeterProvider | None = None


def setup_tracing(service_name: str = "alpha-hunter") -> None:
    """Initialize OpenTelemetry tracing."""
    global _tracer_provider
    _tracer_provider = TracerProvider()
    trace.set_tracer_provider(_tracer_provider)


def get_tracer(name: str = "alpha-hunter") -> trace.Tracer:
    """Get an OTel tracer instance."""
    return trace.get_tracer(name)


def setup_metrics(service_name: str = "alpha-hunter") -> None:
    """Initialize OpenTelemetry metrics."""
    global _meter_provider
    _meter_provider = MeterProvider()
    metrics.set_meter_provider(_meter_provider)


def get_meter(name: str = "alpha-hunter") -> metrics.Meter:
    """Get an OTel meter instance."""
    return metrics.get_meter(name)


# ────────────────────────── Decorators ──────────────────────────


def traced(
    span_name: str | None = None,
    attributes: dict[str, str] | None = None,
) -> Callable:
    """
    Decorator that wraps a function in an OTel span.

    Usage:
        @traced("enrichment.scrape")
        async def scrape_url(url: str) -> str: ...
    """

    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("status", "ok")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = get_tracer()
            with tracer.start_as_current_span(name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "ok")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.message", str(e))
                    span.record_exception(e)
                    raise

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# ────────────────────────── Metrics Definitions ──────────────────────────


class AgentMetrics:
    """Pre-defined metric instruments for agent observability (PRD §14)."""

    def __init__(self) -> None:
        meter = get_meter()

        self.signal_throughput = meter.create_counter(
            "agent.signal.throughput",
            description="Total signals processed",
            unit="1",
        )
        self.qualified_rate = meter.create_counter(
            "agent.signal.qualified",
            description="Signals that passed qualification",
            unit="1",
        )
        self.rejected_rate = meter.create_counter(
            "agent.signal.rejected",
            description="Signals that failed qualification",
            unit="1",
        )
        self.llm_latency = meter.create_histogram(
            "agent.llm.latency",
            description="LLM call latency",
            unit="ms",
        )
        self.llm_schema_failures = meter.create_counter(
            "agent.llm.schema_failures",
            description="LLM responses failing schema validation",
            unit="1",
        )
        self.enrichment_success = meter.create_counter(
            "agent.enrichment.success",
            description="Successful enrichment operations",
            unit="1",
        )
        self.enrichment_failure = meter.create_counter(
            "agent.enrichment.failure",
            description="Failed enrichment operations",
            unit="1",
        )
        self.alert_latency = meter.create_histogram(
            "agent.alert.latency",
            description="Signal-to-alert end-to-end latency",
            unit="ms",
        )
        self.dlq_depth = meter.create_up_down_counter(
            "agent.dlq.depth",
            description="Dead letter queue depth",
            unit="1",
        )
        self.active_tasks = meter.create_up_down_counter(
            "agent.tasks.active",
            description="Currently active orchestration tasks",
            unit="1",
        )


# Singleton metrics instance
_agent_metrics: AgentMetrics | None = None


def get_agent_metrics() -> AgentMetrics:
    """Get singleton AgentMetrics instance."""
    global _agent_metrics
    if _agent_metrics is None:
        _agent_metrics = AgentMetrics()
    return _agent_metrics

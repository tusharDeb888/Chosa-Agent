"""
Domain Exceptions — Structured error types for the agent pipeline.

Each exception carries context for structured logging and tracing.
"""

from __future__ import annotations

from typing import Any


class AlphaHunterError(Exception):
    """Base exception for all Alpha-Hunter errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        self.message = message
        self.context = context or {}
        super().__init__(message)


# ────────────────────────── Agent Lifecycle ──────────────────────────


class AgentStateError(AlphaHunterError):
    """Invalid agent state transition or operation."""
    pass


class KillSwitchActivated(AlphaHunterError):
    """Raised when kill switch blocks a new task."""
    pass


# ────────────────────────── Pipeline Errors ──────────────────────────


class SignalQualificationError(AlphaHunterError):
    """Signal failed qualification criteria."""

    def __init__(self, signal_id: str, reason_code: str, detail: str = ""):
        self.signal_id = signal_id
        self.reason_code = reason_code
        super().__init__(
            f"Signal {signal_id} rejected: {reason_code}",
            context={"signal_id": signal_id, "reason_code": reason_code, "detail": detail},
        )


class EnrichmentError(AlphaHunterError):
    """Error during context enrichment (scraping/retrieval)."""

    def __init__(self, message: str, degraded: bool = False, **kwargs: Any):
        self.degraded = degraded
        super().__init__(message, context={"degraded": degraded, **kwargs})


class DecisionEngineError(AlphaHunterError):
    """Error from the LLM decision engine."""
    pass


class SchemaValidationError(DecisionEngineError):
    """LLM output failed strict schema validation."""

    def __init__(self, message: str, raw_output: str = ""):
        self.raw_output = raw_output
        super().__init__(message, context={"raw_output_length": len(raw_output)})


class LLMUnavailableError(DecisionEngineError):
    """LLM provider is unavailable (circuit breaker open or timeout)."""
    pass


# ────────────────────────── Policy ──────────────────────────


class PolicyViolationError(AlphaHunterError):
    """Decision violated one or more policy constraints."""

    def __init__(self, violation_codes: list[str], message: str = ""):
        self.violation_codes = violation_codes
        super().__init__(
            message or f"Policy violations: {', '.join(violation_codes)}",
            context={"violation_codes": violation_codes},
        )


# ────────────────────────── Infrastructure ──────────────────────────


class StreamError(AlphaHunterError):
    """Redis Streams operation error."""
    pass


class CheckpointError(AlphaHunterError):
    """Checkpoint persistence failure — blocks node completion ack."""
    pass


class CircuitBreakerOpen(AlphaHunterError):
    """Circuit breaker is open — service calls blocked."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(
            f"Circuit breaker open for {service_name}",
            context={"service_name": service_name},
        )


# ────────────────────────── Portfolio ──────────────────────────


class PortfolioError(AlphaHunterError):
    """Error in portfolio operations."""
    pass


class PortfolioStaleError(PortfolioError):
    """Portfolio data is too stale for actionable recommendations."""
    pass


class PortfolioSyncError(PortfolioError):
    """Failed to sync portfolio from broker."""
    pass


# ────────────────────────── Idempotency ──────────────────────────


class DuplicateEventError(AlphaHunterError):
    """Event already processed (idempotency check)."""

    def __init__(self, idempotency_key: str):
        self.idempotency_key = idempotency_key
        super().__init__(
            f"Duplicate event: {idempotency_key}",
            context={"idempotency_key": idempotency_key},
        )

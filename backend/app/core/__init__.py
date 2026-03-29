"""
Core Enums — Single source of truth for all enumeration types.

CRITICAL: AgentState uses EXACTLY these values everywhere (DB, backend, frontend, workers).
No alternate names (STOPPED, ACTIVE, etc.) are permitted.
"""

from __future__ import annotations

from enum import StrEnum


class AgentState(StrEnum):
    """Canonical agent runtime state. Used in DB, Redis, API, and frontend."""

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    TERMINATED = "TERMINATED"
    DEGRADED = "DEGRADED"


class Decision(StrEnum):
    """Recommendation decision type from the LLM synthesis engine."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    WATCH = "WATCH"


class PortfolioMode(StrEnum):
    """Portfolio data source mode."""

    MOCK_JSON = "MOCK_JSON"
    UPSTOX_LIVE = "UPSTOX_LIVE"


class SignalStatus(StrEnum):
    """Signal lifecycle status."""

    CANDIDATE = "CANDIDATE"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"


class StreamTopic(StrEnum):
    """Redis Stream topic names — canonical references."""

    MARKET_TICKS_RAW = "market.ticks.raw"
    SIGNALS_CANDIDATE = "signals.candidate"
    SIGNALS_QUALIFIED = "signals.qualified"
    AGENT_TASKS = "agent.tasks"
    AGENT_DECISIONS = "agent.decisions"
    ALERTS_USER_FEED = "alerts.user_feed"
    DLQ_PREFIX = "dlq"

    @classmethod
    def dlq_for(cls, topic: str) -> str:
        """Generate dead-letter queue topic name for a given topic."""
        return f"dlq.{topic}"


class AnomalyType(StrEnum):
    """Types of market anomalies detected by the ingestion service."""

    VOLUME_SPIKE = "VOLUME_SPIKE"
    PRICE_DEVIATION = "PRICE_DEVIATION"
    SPREAD_ANOMALY = "SPREAD_ANOMALY"
    MOMENTUM_BREAK = "MOMENTUM_BREAK"


class PolicyViolationType(StrEnum):
    """Types of policy violations that can downgrade a decision."""

    MAX_CONCENTRATION_EXCEEDED = "MAX_CONCENTRATION_EXCEEDED"
    DAILY_ACTION_LIMIT_REACHED = "DAILY_ACTION_LIMIT_REACHED"
    CONFIDENCE_BELOW_THRESHOLD = "CONFIDENCE_BELOW_THRESHOLD"
    EVIDENCE_TOO_STALE = "EVIDENCE_TOO_STALE"
    PORTFOLIO_STALE = "PORTFOLIO_STALE"


class WorkerStatus(StrEnum):
    """Worker health status for ops monitoring."""

    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    RESTARTING = "RESTARTING"
    STOPPED = "STOPPED"

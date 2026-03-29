"""
Event Protocol — Envelope, idempotency key generation, and serialization.

Every event flowing through Redis Streams uses this envelope format.
Idempotency key: hash(source + ticker + event_ts + anomaly_type)
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Any, Optional

import orjson
from pydantic import BaseModel, Field


class Event(BaseModel):
    """
    Universal event envelope for Redis Streams.

    All events emitted to any stream use this wrapper to ensure
    consistent idempotency, tracing, and serialization.
    """

    event_id: str = ""
    idempotency_key: str = ""
    topic: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    trace_id: str = ""
    workflow_id: str = ""
    signal_id: str = ""
    user_id: str = ""
    tenant_id: str = "default"
    ticker: str = ""
    attempt: int = 0
    max_attempts: int = 5
    created_at: str = ""

    def model_post_init(self, __context: Any) -> None:
        """Generate event_id and created_at if not set."""
        if not self.event_id:
            self.event_id = f"{self.topic}:{self.ticker}:{int(self.timestamp * 1000)}"
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    @staticmethod
    def generate_idempotency_key(
        source: str,
        ticker: str,
        event_ts: str,
        anomaly_type: str,
    ) -> str:
        """
        Generate deterministic idempotency key per PRD §4.

        Formula: hash(source + ticker + event_ts + anomaly_type)
        """
        raw = f"{source}:{ticker}:{event_ts}:{anomaly_type}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def generate_decision_key(
        user_id: str,
        signal_id: str,
        workflow_version: str = "v1",
    ) -> str:
        """
        Generate idempotent decision key per PRD §12.

        Formula: hash(user_id + signal_id + workflow_version)
        """
        raw = f"{user_id}:{signal_id}:{workflow_version}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def to_stream_dict(self) -> dict[str, str]:
        """Serialize to flat dict suitable for Redis XADD."""
        return {
            "data": orjson.dumps(self.model_dump()).decode(),
            "idempotency_key": self.idempotency_key,
            "event_type": self.event_type,
            "ticker": self.ticker,
            "timestamp": str(self.timestamp),
        }

    @classmethod
    def from_stream_dict(cls, data: dict[str, str]) -> Event:
        """Deserialize from Redis XREADGROUP response."""
        raw = data.get("data", "{}")
        if isinstance(raw, bytes):
            raw = raw.decode()
        parsed = orjson.loads(raw)
        return cls(**parsed)


class EventBatch(BaseModel):
    """A batch of events consumed from a stream."""

    events: list[Event] = Field(default_factory=list)
    stream_id: str = ""
    consumer_group: str = ""
    consumer_name: str = ""

    @property
    def size(self) -> int:
        return len(self.events)

    @property
    def is_empty(self) -> bool:
        return len(self.events) == 0

"""
Test Core Schemas — Validation rules and invariants.

Tests the canonical data contracts used across the entire pipeline.
"""

from datetime import datetime, timezone

import pytest

from app.core.schemas import (
    DecisionOutput,
    PortfolioImpact,
    Citation,
    GuardedDecision,
    EvidenceItem,
    EvidencePack,
    SignalCandidate,
    QualifiedSignal,
)
from app.core.events import Event


class TestDecisionOutputSchema:
    """Test LLM output schema validation rules."""

    def test_confidence_clamped_high(self):
        """Confidence > 100 should be clamped to 100."""
        d = DecisionOutput(
            decision="WATCH",
            confidence=150,
            rationale="Test",
        )
        assert d.confidence == 100

    def test_confidence_clamped_low(self):
        """Confidence < 0 should be clamped to 0."""
        d = DecisionOutput(
            decision="WATCH",
            confidence=-10,
            rationale="Test",
        )
        assert d.confidence == 0

    def test_confidence_float_converted(self):
        """Float confidence should be converted to int."""
        d = DecisionOutput(
            decision="WATCH",
            confidence=72.8,
            rationale="Test",
        )
        assert d.confidence == 72
        assert isinstance(d.confidence, int)

    def test_buy_without_citation_fails(self):
        """BUY decisions MUST include at least one citation."""
        with pytest.raises(ValueError, match="require at least one citation"):
            DecisionOutput(
                decision="BUY",
                confidence=80,
                rationale="Strong buy signal",
                citations=[],
            )

    def test_sell_without_citation_fails(self):
        """SELL decisions MUST include at least one citation."""
        with pytest.raises(ValueError, match="require at least one citation"):
            DecisionOutput(
                decision="SELL",
                confidence=75,
                rationale="Sell signal",
                citations=[],
            )

    def test_watch_without_citation_ok(self):
        """WATCH decisions do not require citations."""
        d = DecisionOutput(
            decision="WATCH",
            confidence=15,
            rationale="Advisory only",
            citations=[],
        )
        assert d.decision == "WATCH"
        assert len(d.citations) == 0

    def test_hold_without_citation_ok(self):
        """HOLD decisions do not require citations."""
        d = DecisionOutput(
            decision="HOLD",
            confidence=50,
            rationale="Position is appropriate",
            citations=[],
        )
        assert d.decision == "HOLD"

    def test_buy_with_citation_passes(self):
        """BUY with citation should pass validation."""
        d = DecisionOutput(
            decision="BUY",
            confidence=80,
            rationale="Strong upside potential",
            citations=[Citation(url="https://moneycontrol.com/tcs")],
        )
        assert d.decision == "BUY"
        assert len(d.citations) == 1

    def test_default_ttl(self):
        """Default TTL should be 300 seconds."""
        d = DecisionOutput(
            decision="WATCH",
            confidence=20,
            rationale="Test",
        )
        assert d.ttl_seconds == 300

    def test_portfolio_impact_defaults(self):
        """Portfolio impact should default to zero."""
        d = DecisionOutput(
            decision="WATCH",
            confidence=20,
            rationale="Test",
        )
        assert d.portfolio_impact.position_delta_pct == 0.0
        assert d.portfolio_impact.cash_impact == 0.0


class TestEvidenceSchema:
    """Test evidence schemas."""

    def test_reliability_score_bounds(self):
        """Reliability score must be between 0 and 1."""
        item = EvidenceItem(
            source_url="https://test.com",
            content="Test content",
            fetched_at=datetime.now(timezone.utc),
            reliability_score=0.8,
        )
        assert 0 <= item.reliability_score <= 1

    def test_reliability_score_above_1_fails(self):
        """Reliability score > 1 should fail validation."""
        with pytest.raises(Exception):
            EvidenceItem(
                source_url="https://test.com",
                content="Test",
                fetched_at=datetime.now(timezone.utc),
                reliability_score=1.5,
            )

    def test_evidence_pack_degraded_flag(self):
        """Evidence pack should track degraded context."""
        pack = EvidencePack(degraded_context=True)
        assert pack.degraded_context is True
        assert len(pack.items) == 0


class TestEventIdempotency:
    """Test event idempotency key generation."""

    def test_same_input_same_key(self):
        """Same inputs should produce the same idempotency key."""
        key1 = Event.generate_idempotency_key("mock", "TCS", "2026-03-28T10:00:00", "VOLUME_SPIKE")
        key2 = Event.generate_idempotency_key("mock", "TCS", "2026-03-28T10:00:00", "VOLUME_SPIKE")
        assert key1 == key2

    def test_different_input_different_key(self):
        """Different inputs should produce different keys."""
        key1 = Event.generate_idempotency_key("mock", "TCS", "2026-03-28T10:00:00", "VOLUME_SPIKE")
        key2 = Event.generate_idempotency_key("mock", "INFY", "2026-03-28T10:00:00", "VOLUME_SPIKE")
        assert key1 != key2

    def test_decision_key_deterministic(self):
        """Decision key should be deterministic."""
        key1 = Event.generate_decision_key("user-1", "sig-abc", "v1")
        key2 = Event.generate_decision_key("user-1", "sig-abc", "v1")
        assert key1 == key2

    def test_decision_key_isolates_users(self):
        """Decision keys must differ across users (tenant isolation)."""
        key1 = Event.generate_decision_key("user-1", "sig-abc", "v1")
        key2 = Event.generate_decision_key("user-2", "sig-abc", "v1")
        assert key1 != key2

    def test_event_serialization_roundtrip(self):
        """Event should survive serialization to/from Redis stream dict."""
        event = Event(
            topic="test.topic",
            event_type="test.event",
            payload={"key": "value"},
            ticker="TCS",
            signal_id="sig-001",
            user_id="user-001",
        )
        stream_dict = event.to_stream_dict()
        restored = Event.from_stream_dict(stream_dict)
        assert restored.topic == "test.topic"
        assert restored.ticker == "TCS"
        assert restored.signal_id == "sig-001"
        assert restored.payload == {"key": "value"}

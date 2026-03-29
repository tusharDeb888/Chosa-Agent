"""
Test Signal Qualification — All 5 PRD §5 criteria.

Tests each qualification rule independently:
1. Data freshness
2. Liquidity threshold
3. Statistical threshold
4. Confidence floor
5. Agent state gate
"""

from datetime import datetime, timezone, timedelta

import pytest

from app.core.schemas import SignalCandidate, QualifiedSignal, RejectedSignal
from app.qualification.service import SignalQualifier


def _make_signal(**overrides) -> SignalCandidate:
    """Factory for valid signal candidates."""
    defaults = {
        "signal_id": "sig-test001",
        "symbol": "ICICIBANK",
        "anomaly_type": "VOLUME_SPIKE",
        "price": 1250.50,
        "volume": 50000,
        "z_score": 3.5,
        "vwap_deviation_pct": 2.1,
        "confidence": 65.0,
        "timestamp": datetime.now(timezone.utc),
        "source": "mock",
    }
    defaults.update(overrides)
    return SignalCandidate(**defaults)


class TestQualificationRules:
    """Test each of the 5 qualification criteria."""

    def setup_method(self):
        self.qualifier = SignalQualifier(
            max_data_age_seconds=30,
            min_volume_threshold=1000,
            min_z_score=2.0,
            min_confidence=30.0,
        )

    def test_valid_signal_qualifies(self):
        """A signal meeting all criteria should pass qualification."""
        signal = _make_signal()
        result = self.qualifier.qualify(signal)
        assert isinstance(result, QualifiedSignal)
        assert result.signal_id == "sig-test001"
        assert result.symbol == "ICICIBANK"

    def test_stale_data_rejected(self):
        """Rule 1: Signals older than max_data_age_seconds should be rejected."""
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=60)
        signal = _make_signal(timestamp=old_ts)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, RejectedSignal)
        assert result.reason_code == "DATA_TOO_STALE"

    def test_low_liquidity_rejected(self):
        """Rule 2: Signals below minimum volume should be rejected."""
        signal = _make_signal(volume=500)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, RejectedSignal)
        assert result.reason_code == "LIQUIDITY_INSUFFICIENT"

    def test_weak_z_score_rejected(self):
        """Rule 3: Signals with z-score below threshold should be rejected."""
        signal = _make_signal(z_score=1.5)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, RejectedSignal)
        assert result.reason_code == "STATISTICAL_THRESHOLD_NOT_MET"

    def test_low_confidence_rejected(self):
        """Rule 4: Signals below confidence floor should be rejected."""
        signal = _make_signal(confidence=20.0)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, RejectedSignal)
        assert result.reason_code == "CONFIDENCE_BELOW_FLOOR"

    def test_agent_not_running_rejected(self):
        """Rule 5: Signals when agent is not RUNNING should be rejected."""
        signal = _make_signal()
        result = self.qualifier.qualify(signal, agent_state="PAUSED")
        assert isinstance(result, RejectedSignal)
        assert result.reason_code == "AGENT_NOT_RUNNING"

    def test_boundary_z_score_passes(self):
        """Boundary: exact threshold z-score should pass."""
        signal = _make_signal(z_score=2.0)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, QualifiedSignal)

    def test_boundary_confidence_passes(self):
        """Boundary: exact threshold confidence should pass."""
        signal = _make_signal(confidence=30.0)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, QualifiedSignal)

    def test_boundary_volume_passes(self):
        """Boundary: exact threshold volume should pass."""
        signal = _make_signal(volume=1000)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, QualifiedSignal)

    def test_negative_z_score_triggers(self):
        """Absolute value of z-score should be checked (bearish signals)."""
        signal = _make_signal(z_score=-3.0)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, QualifiedSignal)

    def test_fresh_timestamp_passes(self):
        """A signal just created should pass freshness check."""
        signal = _make_signal(timestamp=datetime.now(timezone.utc))
        result = self.qualifier.qualify(signal)
        assert isinstance(result, QualifiedSignal)

    def test_rejected_signal_has_detail(self):
        """Rejected signals should include human-readable reason_detail."""
        signal = _make_signal(volume=100)
        result = self.qualifier.qualify(signal)
        assert isinstance(result, RejectedSignal)
        assert "100" in result.reason_detail
        assert "1000" in result.reason_detail

    def test_first_failing_rule_wins(self):
        """When multiple rules fail, the first failing rule's code is returned."""
        signal = _make_signal(volume=100, z_score=0.1, confidence=5.0)
        result = self.qualifier.qualify(signal, agent_state="PAUSED")
        assert isinstance(result, RejectedSignal)
        # Agent state check is first
        assert result.reason_code == "AGENT_NOT_RUNNING"

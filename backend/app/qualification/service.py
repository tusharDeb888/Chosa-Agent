"""
Signal Qualification Service — Applies all 5 criteria per PRD §5.

A signal becomes QualifiedSignal ONLY if ALL are true:
1. Data freshness within allowed skew
2. Liquidity threshold met
3. Statistical threshold breached
4. Confidence >= minimum qualification floor
5. User agent state allows processing (RUNNING only)
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.core.enums import AgentState
from app.core.schemas import SignalCandidate, QualifiedSignal, RejectedSignal
from app.core.observability import get_logger

logger = get_logger("qualification.service")


class QualificationResult:
    """Result of signal qualification."""

    def __init__(
        self,
        passed: bool,
        reason_code: str = "",
        reason_detail: str = "",
    ):
        self.passed = passed
        self.reason_code = reason_code
        self.reason_detail = reason_detail


class SignalQualifier:
    """
    Chain-of-responsibility signal qualification pipeline.

    Each rule returns (pass, reason_code). All must pass.
    """

    def __init__(
        self,
        max_data_age_seconds: int = 30,
        min_volume_threshold: int = 1000,
        min_z_score: float = 2.0,
        min_confidence: float = 30.0,
    ):
        self._max_data_age = max_data_age_seconds
        self._min_volume = min_volume_threshold
        self._min_z_score = min_z_score
        self._min_confidence = min_confidence

    def qualify(
        self,
        signal: SignalCandidate,
        agent_state: str = AgentState.RUNNING,
    ) -> QualifiedSignal | RejectedSignal:
        """
        Run all qualification rules against a signal candidate.

        Returns QualifiedSignal if all pass, RejectedSignal otherwise.
        """
        rules = [
            self._check_agent_state(agent_state),
            self._check_freshness(signal),
            self._check_liquidity(signal),
            self._check_statistical_threshold(signal),
            self._check_confidence(signal),
        ]

        for result in rules:
            if not result.passed:
                logger.info(
                    "signal_rejected",
                    signal_id=signal.signal_id,
                    symbol=signal.symbol,
                    reason=result.reason_code,
                )
                return RejectedSignal(
                    signal_id=signal.signal_id,
                    symbol=signal.symbol,
                    reason_code=result.reason_code,
                    reason_detail=result.reason_detail,
                    timestamp=datetime.now(timezone.utc),
                )

        logger.info(
            "signal_qualified",
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            confidence=signal.confidence,
        )

        return QualifiedSignal(
            signal_id=signal.signal_id,
            symbol=signal.symbol,
            anomaly_type=signal.anomaly_type,
            price=signal.price,
            volume=signal.volume,
            z_score=signal.z_score,
            vwap_deviation_pct=signal.vwap_deviation_pct,
            confidence=signal.confidence,
            timestamp=signal.timestamp,
            source=signal.source,
            qualified_at=datetime.now(timezone.utc),
            metadata=signal.metadata,
        )

    def _check_agent_state(self, state: str) -> QualificationResult:
        """Rule 5: Agent must be in RUNNING state."""
        if state != AgentState.RUNNING:
            return QualificationResult(
                False, "AGENT_NOT_RUNNING", f"Agent state is {state}"
            )
        return QualificationResult(True)

    def _check_freshness(self, signal: SignalCandidate) -> QualificationResult:
        """Rule 1: Data must be within allowed age window."""
        now = datetime.now(timezone.utc)
        signal_ts = signal.timestamp
        if signal_ts.tzinfo is None:
            signal_ts = signal_ts.replace(tzinfo=timezone.utc)

        age = (now - signal_ts).total_seconds()
        if age > self._max_data_age:
            return QualificationResult(
                False, "DATA_TOO_STALE", f"Data age {age:.1f}s exceeds {self._max_data_age}s"
            )
        return QualificationResult(True)

    def _check_liquidity(self, signal: SignalCandidate) -> QualificationResult:
        """Rule 2: Volume must meet minimum threshold."""
        if signal.volume < self._min_volume:
            return QualificationResult(
                False,
                "LIQUIDITY_INSUFFICIENT",
                f"Volume {signal.volume} < min {self._min_volume}",
            )
        return QualificationResult(True)

    def _check_statistical_threshold(
        self, signal: SignalCandidate
    ) -> QualificationResult:
        """Rule 3: Statistical anomaly must be significant."""
        if abs(signal.z_score) < self._min_z_score:
            return QualificationResult(
                False,
                "STATISTICAL_THRESHOLD_NOT_MET",
                f"Z-score {signal.z_score:.2f} < min {self._min_z_score}",
            )
        return QualificationResult(True)

    def _check_confidence(self, signal: SignalCandidate) -> QualificationResult:
        """Rule 4: Confidence must meet floor."""
        if signal.confidence < self._min_confidence:
            return QualificationResult(
                False,
                "CONFIDENCE_BELOW_FLOOR",
                f"Confidence {signal.confidence:.1f} < min {self._min_confidence}",
            )
        return QualificationResult(True)

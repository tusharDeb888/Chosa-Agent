"""
Anomaly Detection — Statistical anomaly detection on market ticks.

Detects volume spikes, price deviations, spread anomalies, and momentum breaks.
Emits SignalCandidate events when thresholds are breached.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.enums import AnomalyType
from app.core.schemas import MarketTick, SignalCandidate
from app.core.observability import get_logger
from app.ingestion.indicators import SlidingWindowIndicator, TickData

logger = get_logger("ingestion.anomaly")


class AnomalyDetector:
    """
    Multi-signal anomaly detector with configurable thresholds.

    Monitors each symbol independently and triggers alerts when
    statistical thresholds are breached.
    """

    def __init__(
        self,
        volume_z_threshold: float = 3.0,
        vwap_deviation_threshold_pct: float = 1.5,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        min_window_size: int = 20,
        window_size: int = 100,
    ):
        self._volume_z_threshold = volume_z_threshold
        self._vwap_deviation_threshold = vwap_deviation_threshold_pct
        self._rsi_oversold = rsi_oversold
        self._rsi_overbought = rsi_overbought
        self._min_window = min_window_size
        self._indicators: dict[str, SlidingWindowIndicator] = {}
        self._window_size = window_size

    def _get_indicator(self, symbol: str) -> SlidingWindowIndicator:
        """Get or create indicator for a symbol."""
        if symbol not in self._indicators:
            self._indicators[symbol] = SlidingWindowIndicator(
                window_size=self._window_size
            )
        return self._indicators[symbol]

    def process_tick(self, tick: MarketTick) -> list[SignalCandidate]:
        """
        Process a market tick and return any detected anomalies.

        Returns empty list if no anomaly detected.
        """
        indicator = self._get_indicator(tick.symbol)
        tick_data = TickData(
            price=tick.price,
            volume=tick.volume,
            timestamp=tick.timestamp.timestamp(),
        )
        indicator.update(tick_data)

        if not indicator.is_ready:
            return []

        signals = []

        # ── Volume Spike Detection ──
        z_score = indicator.volume_z_score(tick.volume)
        if abs(z_score) >= self._volume_z_threshold:
            signals.append(
                self._create_signal(
                    tick=tick,
                    anomaly_type=AnomalyType.VOLUME_SPIKE,
                    z_score=z_score,
                    vwap_deviation=indicator.price_deviation_from_vwap(tick.price),
                    confidence=min(abs(z_score) / 5.0 * 100, 95),
                )
            )

        # ── Price Deviation from VWAP ──
        vwap_dev = indicator.price_deviation_from_vwap(tick.price)
        if abs(vwap_dev) >= self._vwap_deviation_threshold:
            signals.append(
                self._create_signal(
                    tick=tick,
                    anomaly_type=AnomalyType.PRICE_DEVIATION,
                    z_score=z_score,
                    vwap_deviation=vwap_dev,
                    confidence=min(abs(vwap_dev) / 3.0 * 100, 90),
                )
            )

        # ── Momentum Break (RSI extremes) ──
        rsi = indicator.rsi
        if rsi <= self._rsi_oversold or rsi >= self._rsi_overbought:
            signals.append(
                self._create_signal(
                    tick=tick,
                    anomaly_type=AnomalyType.MOMENTUM_BREAK,
                    z_score=z_score,
                    vwap_deviation=vwap_dev,
                    confidence=min(
                        abs(rsi - 50) / 50 * 100, 85
                    ),
                    metadata={"rsi": round(rsi, 2)},
                )
            )

        if signals:
            logger.info(
                "anomalies_detected",
                symbol=tick.symbol,
                count=len(signals),
                types=[s.anomaly_type for s in signals],
            )

        return signals

    def _create_signal(
        self,
        tick: MarketTick,
        anomaly_type: AnomalyType,
        z_score: float,
        vwap_deviation: float,
        confidence: float,
        metadata: dict | None = None,
    ) -> SignalCandidate:
        """Create a SignalCandidate from a detected anomaly."""
        return SignalCandidate(
            signal_id=f"sig-{uuid.uuid4().hex[:12]}",
            symbol=tick.symbol,
            anomaly_type=anomaly_type.value,
            price=tick.price,
            volume=tick.volume,
            z_score=round(z_score, 4),
            vwap_deviation_pct=round(vwap_deviation, 4),
            confidence=round(confidence, 2),
            timestamp=tick.timestamp,
            source=tick.source,
            metadata=metadata or {},
        )

    @property
    def tracked_symbols(self) -> list[str]:
        """List of symbols currently being tracked."""
        return list(self._indicators.keys())

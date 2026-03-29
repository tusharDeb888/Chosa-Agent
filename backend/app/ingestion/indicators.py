"""
Technical Indicators — Sliding window computations for anomaly detection.

All calculations are incremental (no recompute from scratch).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TickData:
    """Minimal tick data for indicator computation."""
    price: float
    volume: int
    timestamp: float


class SlidingWindowIndicator:
    """
    Maintains a sliding window of ticks and computes indicators incrementally.

    Indicators: VWAP, volume mean/std, RSI, price momentum.
    """

    def __init__(self, window_size: int = 100):
        self._window_size = window_size
        self._ticks: deque[TickData] = deque(maxlen=window_size)

        # Running accumulators for O(1) updates
        self._volume_sum: float = 0.0
        self._volume_sq_sum: float = 0.0
        self._pv_sum: float = 0.0  # price * volume sum (for VWAP)
        self._gains: deque[float] = deque(maxlen=window_size)
        self._losses: deque[float] = deque(maxlen=window_size)

    def update(self, tick: TickData) -> None:
        """Add a new tick and update running accumulators."""
        # If window is full, subtract the oldest entry
        if len(self._ticks) == self._window_size:
            oldest = self._ticks[0]
            self._volume_sum -= oldest.volume
            self._volume_sq_sum -= oldest.volume ** 2
            self._pv_sum -= oldest.price * oldest.volume

        # Add price change tracking
        if len(self._ticks) > 0:
            change = tick.price - self._ticks[-1].price
            if change > 0:
                self._gains.append(change)
                self._losses.append(0.0)
            else:
                self._gains.append(0.0)
                self._losses.append(abs(change))

        # Update accumulators
        self._volume_sum += tick.volume
        self._volume_sq_sum += tick.volume ** 2
        self._pv_sum += tick.price * tick.volume

        self._ticks.append(tick)

    @property
    def count(self) -> int:
        return len(self._ticks)

    @property
    def is_ready(self) -> bool:
        """Has enough data accumulated for reliable indicators."""
        return len(self._ticks) >= 20  # Minimum for meaningful stats

    @property
    def vwap(self) -> float:
        """Volume-Weighted Average Price."""
        if self._volume_sum == 0:
            return 0.0
        return self._pv_sum / self._volume_sum

    @property
    def volume_mean(self) -> float:
        """Average volume in the window."""
        n = len(self._ticks)
        if n == 0:
            return 0.0
        return self._volume_sum / n

    @property
    def volume_std(self) -> float:
        """Standard deviation of volume."""
        n = len(self._ticks)
        if n < 2:
            return 0.0
        mean = self.volume_mean
        variance = (self._volume_sq_sum / n) - (mean ** 2)
        return max(variance, 0.0) ** 0.5

    def volume_z_score(self, volume: int) -> float:
        """Z-score of a volume observation relative to the window."""
        std = self.volume_std
        if std == 0:
            return 0.0
        return (volume - self.volume_mean) / std

    def price_deviation_from_vwap(self, price: float) -> float:
        """Percentage deviation of price from VWAP."""
        vwap = self.vwap
        if vwap == 0:
            return 0.0
        return ((price - vwap) / vwap) * 100

    @property
    def rsi(self) -> float:
        """Relative Strength Index (14-period default)."""
        if len(self._gains) < 14:
            return 50.0  # Neutral if insufficient data

        recent_gains = list(self._gains)[-14:]
        recent_losses = list(self._losses)[-14:]

        avg_gain = sum(recent_gains) / 14
        avg_loss = sum(recent_losses) / 14

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @property
    def last_price(self) -> float:
        """Most recent price."""
        if not self._ticks:
            return 0.0
        return self._ticks[-1].price

    @property
    def price_momentum(self) -> float:
        """Price change percentage over the window."""
        if len(self._ticks) < 2:
            return 0.0
        first = self._ticks[0].price
        last = self._ticks[-1].price
        if first == 0:
            return 0.0
        return ((last - first) / first) * 100

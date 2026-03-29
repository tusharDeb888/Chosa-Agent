"""
Mock Market Data Provider — Realistic stochastic tick generation.

Generates volume spikes, spread anomalies, and price deviations
to test the full pipeline in development.
"""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from app.core.schemas import MarketTick
from app.core.observability import get_logger
from app.ingestion.providers import MarketDataProvider

logger = get_logger("ingestion.mock")

# ── Default symbols for mock generation ──
DEFAULT_SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT",
    "WIPRO", "AXISBANK", "BAJFINANCE", "MARUTI", "TATAMOTORS",
    "SUNPHARMA", "TITAN", "NESTLEIND", "ASIANPAINT", "ULTRACEMCO",
]

# ── Base prices for simulation ──
BASE_PRICES = {
    "RELIANCE": 2450.0, "TCS": 3800.0, "INFY": 1550.0,
    "HDFCBANK": 1650.0, "ICICIBANK": 1050.0, "SBIN": 620.0,
    "BHARTIARTL": 1180.0, "ITC": 440.0, "KOTAKBANK": 1760.0,
    "LT": 3400.0, "WIPRO": 480.0, "AXISBANK": 1100.0,
    "BAJFINANCE": 6800.0, "MARUTI": 10500.0, "TATAMOTORS": 780.0,
    "SUNPHARMA": 1250.0, "TITAN": 3200.0, "NESTLEIND": 2350.0,
    "ASIANPAINT": 2800.0, "ULTRACEMCO": 9400.0,
}


class MockProvider(MarketDataProvider):
    """
    Generates realistic market ticks with configurable anomaly injection.

    Features:
    - Brownian motion price simulation
    - Periodic volume spikes (anomalies)
    - Spread widening events
    - Configurable tick interval
    """

    def __init__(
        self,
        symbols: list[str] | None = None,
        tick_interval_ms: int = 500,
        anomaly_probability: float = 0.03,  # 3% chance per tick
        volume_spike_multiplier: float = 5.0,
    ):
        self._symbols = symbols or DEFAULT_SYMBOLS[:10]
        self._tick_interval = tick_interval_ms / 1000.0
        self._anomaly_prob = anomaly_probability
        self._volume_spike_mult = volume_spike_multiplier
        self._connected = False
        self._prices: dict[str, float] = {}
        self._volumes: dict[str, int] = {}
        self._tick_count = 0

    async def connect(self) -> None:
        """Initialize the mock data source."""
        self._connected = True
        for symbol in self._symbols:
            self._prices[symbol] = BASE_PRICES.get(symbol, 1000.0)
            self._volumes[symbol] = random.randint(50000, 200000)
        logger.info("mock_provider_connected", symbols=len(self._symbols))

    async def subscribe(self, symbols: list[str]) -> None:
        """Subscribe to symbols (adds to active set)."""
        for symbol in symbols:
            if symbol not in self._symbols:
                self._symbols.append(symbol)
                self._prices[symbol] = BASE_PRICES.get(symbol, 1000.0)
                self._volumes[symbol] = random.randint(50000, 200000)
        logger.info("mock_subscribed", symbols=symbols)

    async def stream_ticks(self) -> AsyncIterator[MarketTick]:
        """
        Generate continuous market ticks with realistic behavior.

        Price: Brownian motion with drift
        Volume: Log-normal with periodic spikes
        Spread: Normal with occasional widening
        """
        while self._connected:
            for symbol in self._symbols:
                tick = self._generate_tick(symbol)
                yield tick

            self._tick_count += 1
            await asyncio.sleep(self._tick_interval)

    def _generate_tick(self, symbol: str) -> MarketTick:
        """Generate a single realistic tick for a symbol."""
        current_price = self._prices[symbol]
        base_volume = self._volumes[symbol]

        # ── Price movement (Brownian motion) ──
        drift = 0.0001  # Slight upward bias
        volatility = 0.002  # 0.2% per tick
        shock = random.gauss(drift, volatility)
        new_price = current_price * (1 + shock)

        # ── Anomaly injection ──
        is_anomaly = random.random() < self._anomaly_prob
        if is_anomaly:
            # Large price move
            anomaly_shock = random.choice([-1, 1]) * random.uniform(0.01, 0.03)
            new_price = current_price * (1 + anomaly_shock)

        self._prices[symbol] = max(new_price, 1.0)  # Floor at ₹1

        # ── Volume ──
        volume_noise = random.lognormvariate(0, 0.3)
        volume = int(base_volume * volume_noise)
        if is_anomaly:
            volume = int(volume * self._volume_spike_mult)

        # ── Spread ──
        spread_bps = random.uniform(1, 5)  # Normal: 1-5 bps
        if is_anomaly:
            spread_bps = random.uniform(10, 30)  # Anomaly: wider spread

        half_spread = new_price * (spread_bps / 10000)
        bid = new_price - half_spread
        ask = new_price + half_spread

        return MarketTick(
            symbol=symbol,
            price=round(new_price, 2),
            volume=volume,
            bid=round(bid, 2),
            ask=round(ask, 2),
            timestamp=datetime.now(timezone.utc),
            source="mock",
        )

    async def close(self) -> None:
        """Disconnect the mock provider."""
        self._connected = False
        logger.info("mock_provider_disconnected")

    def is_connected(self) -> bool:
        return self._connected

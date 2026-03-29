"""
Market Data Provider — Abstract interface for market data sources.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.core.schemas import MarketTick


class MarketDataProvider(ABC):
    """
    Abstract interface for market data providers.

    Implementations:
    - MockProvider: Stochastic tick generation for dev/test
    - UpstoxProvider: Live Upstox WebSocket V3 (Phase 1 optional)
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source."""
        ...

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None:
        """Subscribe to market data for given symbols."""
        ...

    @abstractmethod
    async def stream_ticks(self) -> AsyncIterator[MarketTick]:
        """Yield market ticks as they arrive."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the connection."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the provider is currently connected."""
        ...

"""
Upstox Market Data Provider — Real data via Upstox REST API.

- During market hours: Polls 1-minute intraday candles every 30s for live ticks
- After market hours: Fetches last trading day's historical candles
- Portfolio: Fetches real holdings from Upstox

Uses Upstox API v2: https://upstox.com/developer/api-documentation
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone, timedelta

import httpx

from app.core.schemas import MarketTick
from app.core.observability import get_logger
from app.ingestion.providers import MarketDataProvider
from app.ingestion.market_hours import is_market_open, get_last_trading_date, IST

logger = get_logger("ingestion.upstox")

UPSTOX_BASE = "https://api.upstox.com/v2"

_ALL_INSTRUMENTS = {}
_ALL_INSTRUMENTS_DETAILS = []

async def get_instrument_keys() -> dict[str, str]:
    """
    Downloads and caches the full Upstox NSE Equity master list.
    Returns: { tradingsymbol: instrument_key }
    """
    global _ALL_INSTRUMENTS, _ALL_INSTRUMENTS_DETAILS
    if _ALL_INSTRUMENTS:
        return _ALL_INSTRUMENTS

    url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.csv.gz"
    try:
        import httpx
        import gzip
        import io
        import csv

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        # Parse CSV from gzip
        with gzip.open(io.BytesIO(resp.content), "rt") as f:
            reader = csv.DictReader(f)
            # Find all EQUITIES
            instruments = {}
            details = []
            for row in reader:
                if row.get("instrument_type") == "EQUITY":
                    tsym = row.get("tradingsymbol", "")
                    ikey = row.get("instrument_key", "")
                    name = row.get("name", "")
                    if tsym and ikey:
                        instruments[tsym] = ikey
                        details.append({"symbol": tsym, "name": name})

            _ALL_INSTRUMENTS = instruments
            _ALL_INSTRUMENTS_DETAILS = details
            logger.info("upstox_instruments_loaded", count=len(instruments))
            return _ALL_INSTRUMENTS
    except Exception as e:
        logger.error("upstox_instruments_load_failed", error=str(e))
        return {}


async def get_instrument_details() -> list[dict]:
    """Returns a list of all NSE Equity details like [{'symbol': 'TCS', 'name': 'Tata Consultancy'}]"""
    if not _ALL_INSTRUMENTS_DETAILS:
        await get_instrument_keys()
    return _ALL_INSTRUMENTS_DETAILS


class UpstoxProvider(MarketDataProvider):
    """
    Real Upstox market data provider.

    - Live mode (market open): Polls intraday candle API every 30s
    - Historical mode (market closed): Fetches last day's data once
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        access_token: str = "",
        symbols: list[str] | None = None,
        poll_interval_seconds: float = 30.0,
    ):
        self._api_key = api_key
        self._api_secret = api_secret
        self._access_token = access_token.strip()
        self._symbols = symbols or ["RELIANCE", "TCS", "HDFCBANK", "INFY"]
        self._poll_interval = poll_interval_seconds
        self._connected = False
        self._client: httpx.AsyncClient | None = None
        self._last_seen_ts: dict[str, str] = {}  # track last candle timestamp per symbol

    @property
    def _headers(self) -> dict:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

    async def connect(self) -> None:
        """Verify access token and establish HTTP client."""
        self._client = httpx.AsyncClient(timeout=15.0)

        # Verify token by fetching profile
        try:
            resp = await self._client.get(
                f"{UPSTOX_BASE}/user/profile",
                headers=self._headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                user_name = data.get("data", {}).get("user_name", "Unknown")
                logger.info("upstox_connected", user=user_name)
                self._connected = True
            else:
                logger.warning(
                    "upstox_auth_check_failed",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                # Still mark connected — token might work for market data
                self._connected = True
        except Exception as e:
            logger.warning("upstox_connect_error", error=str(e))
            self._connected = True  # Try anyway

    async def subscribe(self, symbols: list[str]) -> None:
        """Add symbols to the watch list."""
        for s in symbols:
            if s not in self._symbols:
                self._symbols.append(s)
        logger.info("upstox_subscribed", symbols=symbols)

    async def stream_ticks(self) -> AsyncIterator[MarketTick]:
        """
        Stream real market ticks.

        During market hours: Polls intraday candle API every 30s
        After hours: Replays last trading day's historical candles to keep pipeline alive.
        Loops indefinitely, reconnecting when market opens.
        """
        if not self._client:
            await self.connect()

        logger.info(
            "upstox_stream_starting",
            market_open=is_market_open(),
            symbols=len(self._symbols),
        )

        while self._connected:
            if is_market_open():
                # ── Live mode: poll intraday candles ──
                keys = await get_instrument_keys()
                for symbol in list(self._symbols):
                    instrument_key = keys.get(symbol)
                    if not instrument_key:
                        continue
                    try:
                        ticks = await self._fetch_intraday_candle(symbol, instrument_key)
                        for tick in ticks:
                            yield tick
                    except Exception as e:
                        logger.warning("upstox_candle_fetch_error", symbol=symbol, error=str(e))
                await asyncio.sleep(self._poll_interval)
            else:
                # ── Historical replay mode: use last trading day's data ──
                logger.info(
                    "upstox_historical_replay_mode",
                    reason="market_closed",
                    last_trading_date=get_last_trading_date(),
                    symbols=len(self._symbols),
                )
                keys = await get_instrument_keys()
                for symbol in list(self._symbols):
                    instrument_key = keys.get(symbol)
                    if not instrument_key:
                        continue
                    try:
                        ticks = await self._fetch_historical_ticks(symbol, instrument_key)
                        for tick in ticks:
                            if not self._connected:
                                return
                            yield tick
                            # Throttle to avoid overwhelming the pipeline
                            await asyncio.sleep(2)
                    except Exception as e:
                        logger.warning("upstox_historical_replay_error", symbol=symbol, error=str(e))

                # After replaying all symbols, sleep before next replay cycle
                logger.info("upstox_historical_replay_cycle_complete", symbols=len(self._symbols))
                await asyncio.sleep(60)  # 1 minute between replay cycles

    async def _fetch_intraday_candle(
        self, symbol: str, instrument_key: str
    ) -> list[MarketTick]:
        """Fetch latest 1-minute intraday candles from Upstox API."""
        url = f"{UPSTOX_BASE}/historical-candle/intraday/{instrument_key}/1minute"

        resp = await self._client.get(url, headers=self._headers)
        if resp.status_code != 200:
            logger.warning(
                "upstox_candle_api_error",
                symbol=symbol,
                status=resp.status_code,
            )
            return []

        data = resp.json()
        candles = data.get("data", {}).get("candles", [])
        if not candles:
            return []

        ticks = []
        last_seen = self._last_seen_ts.get(symbol)

        for candle in candles:
            # Candle format: [timestamp, open, high, low, close, volume, oi]
            ts_str = candle[0]

            # Skip already-seen candles
            if last_seen and ts_str <= last_seen:
                continue

            price = candle[4]  # close price
            high = candle[2]
            low = candle[3]
            volume = candle[5]

            # Approximate bid/ask from high/low
            spread = max((high - low) * 0.1, price * 0.0001)
            bid = round(price - spread / 2, 2)
            ask = round(price + spread / 2, 2)

            tick = MarketTick(
                symbol=symbol,
                price=round(price, 2),
                volume=int(volume),
                bid=bid,
                ask=ask,
                timestamp=datetime.fromisoformat(ts_str.replace("T", "T")),
                source="upstox",
            )
            ticks.append(tick)

        # Update last seen timestamp
        if candles:
            self._last_seen_ts[symbol] = candles[0][0]  # Most recent candle

        return ticks

    async def _fetch_historical_ticks(
        self, symbol: str, instrument_key: str
    ) -> list[MarketTick]:
        """
        Fetch last trading day's 1-minute candles and convert to MarketTick objects.
        Used for historical replay mode when market is closed.
        """
        last_date = get_last_trading_date()
        url = f"{UPSTOX_BASE}/historical-candle/{instrument_key}/1minute/{last_date}/{last_date}"

        try:
            resp = await self._client.get(url, headers=self._headers)
            if resp.status_code != 200:
                logger.warning(
                    "upstox_historical_ticks_error",
                    symbol=symbol,
                    status=resp.status_code,
                    date=last_date,
                )
                return []

            data = resp.json()
            candles = data.get("data", {}).get("candles", [])
            if not candles:
                return []

            ticks = []
            for candle in candles:
                ts_str = candle[0]
                price = candle[4]  # close
                high = candle[2]
                low = candle[3]
                volume = candle[5]

                spread = max((high - low) * 0.1, price * 0.0001)
                tick = MarketTick(
                    symbol=symbol,
                    price=round(price, 2),
                    volume=int(volume),
                    bid=round(price - spread / 2, 2),
                    ask=round(price + spread / 2, 2),
                    timestamp=datetime.fromisoformat(ts_str),
                    source="upstox_historical",
                )
                ticks.append(tick)

            logger.info(
                "upstox_historical_ticks_loaded",
                symbol=symbol,
                date=last_date,
                count=len(ticks),
            )
            return ticks

        except Exception as e:
            logger.warning("upstox_historical_ticks_fetch_error", symbol=symbol, error=str(e))
            return []

    async def fetch_historical_candles(
        self, symbol: str, date: str | None = None, interval: str = "1minute"
    ) -> list[dict]:
        """
        Fetch historical candle data for a symbol.

        Returns raw candle data: [[timestamp, open, high, low, close, volume, oi], ...]
        """
        if not self._client:
            await self.connect()

        keys = await get_instrument_keys()
        instrument_key = keys.get(symbol)
        if not instrument_key:
            return []

        if date is None:
            date = get_last_trading_date()

        url = f"{UPSTOX_BASE}/historical-candle/{instrument_key}/{interval}/{date}/{date}"

        try:
            resp = await self._client.get(url, headers=self._headers)
            if resp.status_code == 200:
                data = resp.json()
                candles = data.get("data", {}).get("candles", [])
                return [
                    {
                        "timestamp": c[0],
                        "open": c[1],
                        "high": c[2],
                        "low": c[3],
                        "close": c[4],
                        "volume": c[5],
                        "oi": c[6] if len(c) > 6 else 0,
                    }
                    for c in candles
                ]
            else:
                logger.warning(
                    "upstox_historical_error",
                    symbol=symbol,
                    status=resp.status_code,
                )
                return []
        except Exception as e:
            logger.warning("upstox_historical_fetch_error", symbol=symbol, error=str(e))
            return []

    async def fetch_range_candles(
        self, symbol: str, from_date: str, to_date: str, interval: str = "day"
    ) -> list[dict]:
        """
        Fetch historical candle data across a date range (e.g. 30 days).
        Used for multi-day charts in the portfolio section.
        """
        if not self._client:
            await self.connect()

        keys = await get_instrument_keys()
        instrument_key = keys.get(symbol)
        if not instrument_key:
            return []

        url = f"{UPSTOX_BASE}/historical-candle/{instrument_key}/{interval}/{to_date}/{from_date}"

        try:
            resp = await self._client.get(url, headers=self._headers)
            if resp.status_code == 200:
                data = resp.json()
                candles = data.get("data", {}).get("candles", [])
                return [
                    {
                        "timestamp": c[0],
                        "open": c[1],
                        "high": c[2],
                        "low": c[3],
                        "close": c[4],
                        "volume": c[5],
                        "oi": c[6] if len(c) > 6 else 0,
                    }
                    for c in candles
                ]
            else:
                logger.warning(
                    "upstox_range_candle_error",
                    symbol=symbol,
                    status=resp.status_code,
                )
                return []
        except Exception as e:
            logger.warning("upstox_range_candle_fetch_error", symbol=symbol, error=str(e))
            return []

    async def fetch_holdings(self) -> list[dict]:
        """Fetch real portfolio holdings from Upstox."""
        if not self._client:
            await self.connect()

        try:
            resp = await self._client.get(
                f"{UPSTOX_BASE}/portfolio/long-term-holdings",
                headers=self._headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                holdings = data.get("data", [])
                logger.info("upstox_holdings_fetched", count=len(holdings))
                return holdings
            else:
                logger.warning(
                    "upstox_holdings_error",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                return []
        except Exception as e:
            logger.warning("upstox_holdings_fetch_error", error=str(e))
            return []

    async def fetch_positions(self) -> list[dict]:
        """Fetch current day positions from Upstox."""
        if not self._client:
            await self.connect()

        try:
            resp = await self._client.get(
                f"{UPSTOX_BASE}/portfolio/short-term-positions",
                headers=self._headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                positions = data.get("data", [])
                logger.info("upstox_positions_fetched", count=len(positions))
                return positions
            else:
                return []
        except Exception as e:
            logger.warning("upstox_positions_fetch_error", error=str(e))
            return []

    async def close(self) -> None:
        """Close the HTTP client."""
        self._connected = False
        if self._client:
            await self._client.aclose()
            self._client = None
        logger.info("upstox_provider_disconnected")

    def is_connected(self) -> bool:
        return self._connected

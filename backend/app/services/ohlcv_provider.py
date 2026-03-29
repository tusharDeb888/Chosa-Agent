"""
OHLCV Provider — Async data fetcher that wraps UpstoxProvider.

Converts raw candle dicts into pandas DataFrames with proper OHLCV columns
and DatetimeIndex, suitable for pandas_ta and vectorbt consumption.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from app.config import get_settings
from app.core.observability import get_logger
from app.ingestion.market_hours import get_last_trading_date

logger = get_logger("services.ohlcv")


async def fetch_ohlcv(
    ticker: str,
    interval: str = "day",
    lookback_days: int = 365,
) -> pd.DataFrame:
    """
    Fetch OHLCV data for a ticker and return as a pandas DataFrame.

    Args:
        ticker: NSE symbol (e.g. "RELIANCE")
        interval: Candle interval ("1minute", "30minute", "day")
        lookback_days: Number of calendar days to look back

    Returns:
        DataFrame with columns: open, high, low, close, volume
        DatetimeIndex sorted ascending (oldest first)
    """
    settings = get_settings()

    if not settings.upstox_access_token:
        logger.warning("ohlcv_no_token", ticker=ticker)
        return pd.DataFrame()

    from app.ingestion.providers.upstox import UpstoxProvider
    from datetime import datetime, timedelta

    provider = UpstoxProvider(
        api_key=settings.upstox_api_key,
        api_secret=settings.upstox_api_secret,
        access_token=settings.upstox_access_token,
    )

    try:
        end_date = get_last_trading_date()
        start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=int(lookback_days * 1.6))
        start_date = start_dt.strftime("%Y-%m-%d")

        candles = await provider.fetch_range_candles(
            symbol=ticker.upper(),
            from_date=start_date,
            to_date=end_date,
            interval=interval,
        )

        if not candles:
            logger.warning("ohlcv_no_data", ticker=ticker, lookback=lookback_days)
            return pd.DataFrame()

        df = pd.DataFrame(candles)

        # Normalize column names
        col_map = {}
        for col in df.columns:
            lower = col.lower()
            if lower in ("open", "high", "low", "close", "volume", "timestamp"):
                col_map[col] = lower
        df = df.rename(columns=col_map)

        # Ensure required columns exist
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(set(df.columns)):
            missing = required - set(df.columns)
            logger.error("ohlcv_missing_columns", ticker=ticker, missing=list(missing))
            return pd.DataFrame()

        # Set datetime index
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.set_index("timestamp")
        else:
            df.index = pd.to_datetime(df.index)

        # Sort ascending (oldest first — required by pandas_ta)
        df = df.sort_index(ascending=True)

        # Ensure numeric types
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.dropna(subset=["open", "high", "low", "close"])

        logger.info("ohlcv_fetched", ticker=ticker, bars=len(df), interval=interval)
        return df

    except Exception as e:
        logger.error("ohlcv_fetch_error", ticker=ticker, error=str(e))
        return pd.DataFrame()
    finally:
        await provider.close()

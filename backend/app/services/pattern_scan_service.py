"""
Pattern Scan Service — MACD divergence + MA crossover detection + backtest.

All heavy compute is run synchronously and must be
called from run_in_threadpool() at the API layer.

Pipeline:
  1. Receive OHLCV DataFrame
  2. Compute MACD and Moving Average indicators (pandas_ta)
  3. Detect divergence + crossover signals
  4. Generate entry/exit boolean arrays
  5. Run vectorbt.Portfolio.from_signals()
  6. Extract metrics
  7. Summarize with LLM
"""

from __future__ import annotations

import time
from typing import Tuple, Optional

import numpy as np
import pandas as pd

from app.config import get_settings
from app.core.observability import get_logger
from app.schemas.patterns import (
    PatternSignalFlags,
    BacktestMetrics,
    PatternScanResponse,
)

logger = get_logger("services.pattern_scan")


# ─────────────────────────── Indicator Computation ───────────────────────────


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add MACD and Moving Average columns to the DataFrame.
    Pure-pandas implementation — no pandas_ta or numba dependency.
    """
    close = df["close"]

    # MACD (12, 26, 9) — pure pandas EWM
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    df["MACD_12_26_9"] = macd_line
    df["MACDs_12_26_9"] = signal_line
    df["MACDh_12_26_9"] = macd_hist

    # Simple Moving Averages
    df["SMA_50"] = close.rolling(window=50).mean()
    df["SMA_200"] = close.rolling(window=200).mean()

    # EMA for additional crossover strength
    df["EMA_12"] = ema_12
    df["EMA_26"] = ema_26

    return df


# ─────────────────────────── Signal Detection ───────────────────────────


def detect_macd_divergence(df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
    """
    Detect bullish/bearish MACD divergence.

    Bullish divergence: Price makes lower low, MACD histogram makes higher low
    Bearish divergence: Price makes higher high, MACD histogram makes lower high

    Returns: (detected: bool, type: 'bullish' | 'bearish' | None)
    """
    hist_col = None
    for col in df.columns:
        if "MACDh" in col or "MACD_hist" in col.replace(" ", "_"):
            hist_col = col
            break

    if hist_col is None or hist_col not in df.columns:
        return False, None

    hist = df[hist_col].dropna()
    close = df["close"].loc[hist.index]

    if len(hist) < 30:
        return False, None

    # Look at last 30 bars for divergence
    recent = 30
    h = hist.iloc[-recent:].values
    c = close.iloc[-recent:].values

    # Find local minima/maxima in histogram
    # Bullish: price lower low + histogram higher low (last 2 troughs)
    troughs_idx = []
    for i in range(1, len(h) - 1):
        if h[i] < h[i - 1] and h[i] < h[i + 1] and h[i] < 0:
            troughs_idx.append(i)

    if len(troughs_idx) >= 2:
        t1, t2 = troughs_idx[-2], troughs_idx[-1]
        # Bullish divergence: price lower, historgram higher
        if c[t2] < c[t1] and h[t2] > h[t1]:
            return True, "bullish"

    # Bearish: price higher high + histogram lower high
    peaks_idx = []
    for i in range(1, len(h) - 1):
        if h[i] > h[i - 1] and h[i] > h[i + 1] and h[i] > 0:
            peaks_idx.append(i)

    if len(peaks_idx) >= 2:
        p1, p2 = peaks_idx[-2], peaks_idx[-1]
        if c[p2] > c[p1] and h[p2] < h[p1]:
            return True, "bearish"

    return False, None


def detect_ma_crossover(df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
    """
    Detect golden cross (bullish) or death cross (bearish).

    Golden cross: SMA50 crosses above SMA200
    Death cross: SMA50 crosses below SMA200

    Checks the most recent 10 bars for a crossover event.
    """
    if "SMA_50" not in df.columns or "SMA_200" not in df.columns:
        return False, None

    sma50 = df["SMA_50"].dropna()
    sma200 = df["SMA_200"].dropna()

    if len(sma50) < 10 or len(sma200) < 10:
        return False, None

    # Align
    common_idx = sma50.index.intersection(sma200.index)
    if len(common_idx) < 10:
        return False, None

    s50 = sma50.loc[common_idx].iloc[-10:]
    s200 = sma200.loc[common_idx].iloc[-10:]

    # Check for crossover in the last 10 bars
    diff = s50 - s200
    for i in range(1, len(diff)):
        prev_val = diff.iloc[i - 1]
        curr_val = diff.iloc[i]

        if prev_val <= 0 and curr_val > 0:
            return True, "golden_cross"
        if prev_val >= 0 and curr_val < 0:
            return True, "death_cross"

    return False, None


# ─────────────────────────── Entry/Exit Signal Generation ───────────────────────────


def generate_signals(df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    """
    Generate boolean entry/exit signal arrays for vectorbt backtesting.

    Entry: MACD histogram crosses above 0 (bullish momentum)
    Exit: MACD histogram crosses below 0 (bearish momentum)
    """
    hist_col = None
    for col in df.columns:
        if "MACDh" in col or "MACD_hist" in col.replace(" ", "_"):
            hist_col = col
            break

    if hist_col is None:
        return pd.Series(False, index=df.index), pd.Series(False, index=df.index)

    hist = df[hist_col].fillna(0)

    entries = (hist > 0) & (hist.shift(1) <= 0)
    exits = (hist < 0) & (hist.shift(1) >= 0)

    return entries, exits


# ─────────────────────────── Backtesting ───────────────────────────


def run_backtest(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
    init_cash: float = 1_000_000.0,
) -> BacktestMetrics:
    """
    Run vectorized backtest using vectorbt.

    Lazy imports vectorbt — must be called from threadpool.
    """
    try:
        import vectorbt as vbt

        # Align all series
        common_idx = close.index.intersection(entries.index).intersection(exits.index)
        c = close.loc[common_idx]
        e = entries.loc[common_idx]
        x = exits.loc[common_idx]

        if e.sum() == 0:
            return BacktestMetrics(total_trades=0)

        pf = vbt.Portfolio.from_signals(
            close=c,
            entries=e,
            exits=x,
            init_cash=init_cash,
            freq="1D",
        )

        stats = pf.stats()

        win_rate = float(stats.get("Win Rate [%]", 0) or 0)
        avg_return = float(stats.get("Expectancy", 0) or 0)
        max_dd = float(stats.get("Max Drawdown [%]", 0) or 0)
        total_trades = int(stats.get("Total Trades", 0) or 0)
        sharpe = stats.get("Sharpe Ratio", None)
        profit_factor = stats.get("Profit Factor", None)

        return BacktestMetrics(
            win_rate_pct=round(win_rate, 2),
            avg_return_pct=round(avg_return, 4),
            max_drawdown_pct=round(-abs(max_dd), 2),
            total_trades=total_trades,
            sharpe_ratio=round(float(sharpe), 3) if sharpe is not None and not np.isnan(sharpe) else None,
            profit_factor=round(float(profit_factor), 3) if profit_factor is not None and not np.isnan(profit_factor) else None,
        )

    except ImportError:
        logger.warning("vectorbt_not_installed")
        return _fallback_backtest(close, entries, exits)
    except Exception as e:
        logger.error("backtest_error", error=str(e))
        return _fallback_backtest(close, entries, exits)


def _fallback_backtest(
    close: pd.Series,
    entries: pd.Series,
    exits: pd.Series,
) -> BacktestMetrics:
    """
    Pure-pandas fallback backtester when vectorbt is unavailable.
    Simulates long-only trades from entry to exit signals.
    """
    try:
        trades = []
        in_trade = False
        entry_price = 0.0

        for i in range(len(close)):
            if entries.iloc[i] and not in_trade:
                entry_price = close.iloc[i]
                in_trade = True
            elif exits.iloc[i] and in_trade:
                exit_price = close.iloc[i]
                pnl_pct = (exit_price - entry_price) / entry_price * 100
                trades.append(pnl_pct)
                in_trade = False

        if not trades:
            return BacktestMetrics(total_trades=0)

        wins = [t for t in trades if t > 0]
        win_rate = len(wins) / len(trades) * 100
        avg_return = sum(trades) / len(trades)

        # Approximate max drawdown
        equity = [100]
        for t in trades:
            equity.append(equity[-1] * (1 + t / 100))
        peak = equity[0]
        max_dd = 0
        for v in equity:
            if v > peak:
                peak = v
            dd = (v - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd

        return BacktestMetrics(
            win_rate_pct=round(win_rate, 2),
            avg_return_pct=round(avg_return, 4),
            max_drawdown_pct=round(max_dd, 2),
            total_trades=len(trades),
        )
    except Exception as e:
        logger.error("fallback_backtest_error", error=str(e))
        return BacktestMetrics(total_trades=0)


# ─────────────────────────── LLM Summarization ───────────────────────────


async def summarize_with_llm(
    ticker: str,
    signals: PatternSignalFlags,
    backtest: BacktestMetrics,
) -> str:
    """
    Use Groq LLM to generate a 2-sentence plain English summary.
    Falls back to a template if LLM is unavailable.
    """
    settings = get_settings()

    if not settings.groq_api_key:
        return _template_summary(ticker, signals, backtest)

    try:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=settings.groq_api_key)

        prompt = f"""You are a financial analyst. Summarize these technical analysis findings in exactly 2 sentences of plain English that a retail investor can understand. No jargon.

Ticker: {ticker}
MACD Divergence Detected: {signals.macd_divergence} ({signals.macd_crossover_type or 'none'})
MA Crossover Detected: {signals.ma_crossover} ({signals.ma_crossover_type or 'none'})
Backtest Win Rate: {backtest.win_rate_pct}%
Average Return per Trade: {backtest.avg_return_pct}%
Maximum Drawdown: {backtest.max_drawdown_pct}%
Total Trades in Backtest: {backtest.total_trades}

Write exactly 2 sentences. Be specific about what the patterns mean for the investor."""

        response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You are a concise market analyst. Always reply in exactly 2 sentences."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0.3,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning("llm_summary_fallback", error=str(e))
        return _template_summary(ticker, signals, backtest)


def _template_summary(ticker: str, signals: PatternSignalFlags, backtest: BacktestMetrics) -> str:
    """Deterministic template fallback when LLM is unavailable."""
    parts = []

    if signals.macd_divergence:
        direction = "upward" if signals.macd_crossover_type == "bullish" else "downward"
        parts.append(f"{ticker} shows a {signals.macd_crossover_type} MACD divergence suggesting a potential {direction} trend shift")

    if signals.ma_crossover:
        if signals.ma_crossover_type == "golden_cross":
            parts.append(f"a golden cross (50-day moving average crossing above 200-day) confirms building bullish momentum")
        else:
            parts.append(f"a death cross (50-day moving average crossing below 200-day) signals weakening trend")

    if not parts:
        parts.append(f"No strong technical patterns detected for {ticker} in the analyzed period")

    if backtest.total_trades > 0:
        parts.append(
            f"Backtesting this pattern over {backtest.total_trades} historical trades shows "
            f"a {backtest.win_rate_pct}% win rate with {backtest.max_drawdown_pct}% maximum drawdown"
        )
    else:
        parts.append("Insufficient trade signals for backtesting")

    return ". ".join(parts[:2]) + "."


# ─────────────────────────── Full Scan Pipeline (sync) ───────────────────────────


def scan_sync(df: pd.DataFrame, ticker: str) -> dict:
    """
    Synchronous full scan pipeline. Must be run in threadpool.

    Returns dict with signals, backtest, and timing.
    """
    t0 = time.time()

    # Step 1: Compute indicators
    df = compute_indicators(df)

    # Step 2: Detect patterns
    macd_div, macd_type = detect_macd_divergence(df)
    ma_cross, ma_type = detect_ma_crossover(df)

    signals = PatternSignalFlags(
        macd_divergence=macd_div,
        macd_crossover_type=macd_type,
        ma_crossover=ma_cross,
        ma_crossover_type=ma_type,
    )

    # Step 3: Generate entry/exit signals for backtest
    entries, exits = generate_signals(df)

    # Step 4: Run backtest
    backtest = run_backtest(df["close"], entries, exits)

    elapsed_ms = (time.time() - t0) * 1000

    return {
        "signals": signals,
        "backtest": backtest,
        "data_points": len(df),
        "elapsed_ms": round(elapsed_ms, 2),
    }

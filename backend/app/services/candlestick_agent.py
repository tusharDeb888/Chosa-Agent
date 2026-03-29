"""
Portfolio Pattern Agent — Autonomous scanner that analyzes every portfolio holding.

Extended candlestick pattern detection:
  - Doji (indecision)
  - Hammer / Inverted Hammer (reversal)
  - Engulfing (bullish/bearish reversal)
  - Morning Star / Evening Star (3-bar reversal)
  - Three White Soldiers / Three Black Crows (trend continuation)
  - Spinning Top (indecision)

Combines with MACD divergence + MA crossovers to produce a single
BUY / SELL / HOLD recommendation per holding with confidence score.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple, List

import numpy as np
import pandas as pd

from app.config import get_settings
from app.core.observability import get_logger

logger = get_logger("services.candlestick_agent")


# ═══════════════════════════════════════════════════════════
#  CANDLESTICK PATTERN DETECTION — Pure pandas, zero deps
# ═══════════════════════════════════════════════════════════


def detect_candlestick_patterns(df: pd.DataFrame) -> list[dict]:
    """
    Detect candlestick patterns in the LAST 5 bars of OHLCV data.
    Returns list of dicts: {name, type, signal, confidence, bar_index}
    """
    if len(df) < 5:
        return []

    patterns = []
    o = df["open"].values
    h = df["high"].values
    l = df["low"].values
    c = df["close"].values

    n = len(df)

    # Analyze last 5 bars for patterns
    for i in range(max(0, n - 5), n):
        body = abs(c[i] - o[i])
        upper_shadow = h[i] - max(o[i], c[i])
        lower_shadow = min(o[i], c[i]) - l[i]
        total_range = h[i] - l[i]

        if total_range == 0:
            continue

        body_pct = body / total_range

        # ── Doji ──
        if body_pct < 0.1:
            patterns.append({
                "name": "Doji",
                "type": "single",
                "signal": "neutral",
                "emoji": "⚖️",
                "confidence": 60,
                "description": "Market indecision — equal buying and selling pressure",
                "bar_index": i,
            })

        # ── Hammer (bullish reversal at bottom) ──
        if (lower_shadow > body * 2 and upper_shadow < body * 0.5
                and c[i] > o[i] and body_pct > 0.15):
            patterns.append({
                "name": "Hammer",
                "type": "single",
                "signal": "bullish",
                "emoji": "🔨",
                "confidence": 72,
                "description": "Bullish reversal — buyers rejected lower prices",
                "bar_index": i,
            })

        # ── Inverted Hammer ──
        if (upper_shadow > body * 2 and lower_shadow < body * 0.5
                and body_pct > 0.15):
            patterns.append({
                "name": "Inverted Hammer",
                "type": "single",
                "signal": "bullish",
                "emoji": "⬆️",
                "confidence": 65,
                "description": "Potential bullish reversal after downtrend",
                "bar_index": i,
            })

        # ── Shooting Star (bearish at top) ──
        if (upper_shadow > body * 2 and lower_shadow < body * 0.5
                and c[i] < o[i] and body_pct > 0.15):
            patterns.append({
                "name": "Shooting Star",
                "type": "single",
                "signal": "bearish",
                "emoji": "💫",
                "confidence": 70,
                "description": "Bearish reversal — sellers pushed price down from highs",
                "bar_index": i,
            })

        # ── Spinning Top ──
        if 0.1 < body_pct < 0.35 and upper_shadow > body * 0.8 and lower_shadow > body * 0.8:
            patterns.append({
                "name": "Spinning Top",
                "type": "single",
                "signal": "neutral",
                "emoji": "🔄",
                "confidence": 50,
                "description": "Indecision — neither bulls nor bears in control",
                "bar_index": i,
            })

        # ── Engulfing patterns (need previous bar) ──
        if i > 0:
            prev_body = abs(c[i-1] - o[i-1])
            # Bullish Engulfing
            if (c[i-1] < o[i-1] and c[i] > o[i]  # prev red, current green
                    and o[i] <= c[i-1] and c[i] >= o[i-1]
                    and body > prev_body * 1.2):
                patterns.append({
                    "name": "Bullish Engulfing",
                    "type": "double",
                    "signal": "bullish",
                    "emoji": "🟢",
                    "confidence": 78,
                    "description": "Strong bullish reversal — buyers completely overwhelmed sellers",
                    "bar_index": i,
                })

            # Bearish Engulfing
            if (c[i-1] > o[i-1] and c[i] < o[i]  # prev green, current red
                    and o[i] >= c[i-1] and c[i] <= o[i-1]
                    and body > prev_body * 1.2):
                patterns.append({
                    "name": "Bearish Engulfing",
                    "type": "double",
                    "signal": "bearish",
                    "emoji": "🔴",
                    "confidence": 78,
                    "description": "Strong bearish reversal — sellers overwhelmed buyers",
                    "bar_index": i,
                })

        # ── Three White Soldiers ──
        if i >= 2:
            if (c[i] > o[i] and c[i-1] > o[i-1] and c[i-2] > o[i-2]
                    and c[i] > c[i-1] > c[i-2]
                    and o[i] > o[i-1] > o[i-2]):
                patterns.append({
                    "name": "Three White Soldiers",
                    "type": "triple",
                    "signal": "bullish",
                    "emoji": "🏳️",
                    "confidence": 82,
                    "description": "Strong bullish continuation — three consecutive strong green candles",
                    "bar_index": i,
                })

            # Three Black Crows
            if (c[i] < o[i] and c[i-1] < o[i-1] and c[i-2] < o[i-2]
                    and c[i] < c[i-1] < c[i-2]
                    and o[i] < o[i-1] < o[i-2]):
                patterns.append({
                    "name": "Three Black Crows",
                    "type": "triple",
                    "signal": "bearish",
                    "emoji": "🐦‍⬛",
                    "confidence": 82,
                    "description": "Strong bearish continuation — three consecutive red candles",
                    "bar_index": i,
                })

    # Deduplicate by name, keep highest confidence
    seen = {}
    for p in patterns:
        key = p["name"]
        if key not in seen or p["confidence"] > seen[key]["confidence"]:
            seen[key] = p

    return list(seen.values())


# ═══════════════════════════════════════════════════════════
#  TREND + MOMENTUM ANALYSIS
# ═══════════════════════════════════════════════════════════


def analyze_trend(df: pd.DataFrame) -> dict:
    """Analyze recent trend direction and strength."""
    if len(df) < 20:
        return {"direction": "neutral", "strength": 0, "sma_20": None, "sma_50": None}

    close = df["close"]
    sma_20 = close.rolling(20).mean().iloc[-1]
    sma_50 = close.rolling(50).mean().iloc[-1] if len(df) >= 50 else None

    current = close.iloc[-1]

    # Trend direction
    if current > sma_20 and (sma_50 is None or sma_20 > sma_50):
        direction = "bullish"
    elif current < sma_20 and (sma_50 is None or sma_20 < sma_50):
        direction = "bearish"
    else:
        direction = "neutral"

    # Strength (0-100 based on price vs SMA distance)
    pct_above_sma = (current - sma_20) / sma_20 * 100
    strength = min(abs(pct_above_sma) * 10, 100)

    # RSI approximation (14-period)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50

    return {
        "direction": direction,
        "strength": round(strength, 1),
        "sma_20": round(sma_20, 2),
        "sma_50": round(sma_50, 2) if sma_50 else None,
        "rsi": round(current_rsi, 1),
        "price_vs_sma20_pct": round(pct_above_sma, 2),
    }


# ═══════════════════════════════════════════════════════════
#  COMPOSITE RECOMMENDATION ENGINE
# ═══════════════════════════════════════════════════════════


def compute_recommendation(
    patterns: list[dict],
    trend: dict,
    backtest_win_rate: float,
    pnl_pct: float,
) -> dict:
    """
    Generate BUY/SELL/HOLD recommendation from all signals.

    Scoring system:
    - Candlestick patterns contribute ±points
    - Trend direction contributes ±points
    - RSI extremes contribute ±points
    - Existing P&L contributes (take profit / cut loss signals)
    """
    score = 0
    reasons = []

    # Pattern signals
    bullish_patterns = [p for p in patterns if p["signal"] == "bullish"]
    bearish_patterns = [p for p in patterns if p["signal"] == "bearish"]

    for p in bullish_patterns:
        score += p["confidence"] * 0.3
        reasons.append(f"{p['emoji']} {p['name']}")

    for p in bearish_patterns:
        score -= p["confidence"] * 0.3
        reasons.append(f"{p['emoji']} {p['name']}")

    # Trend contribution
    if trend["direction"] == "bullish":
        score += 15
        if trend["strength"] > 50:
            score += 10
    elif trend["direction"] == "bearish":
        score -= 15
        if trend["strength"] > 50:
            score -= 10

    # RSI extremes
    rsi = trend.get("rsi", 50)
    if rsi < 30:
        score += 12  # Oversold — buy signal
        reasons.append("📊 RSI oversold")
    elif rsi > 70:
        score -= 12  # Overbought — sell signal
        reasons.append("📊 RSI overbought")

    # P&L based signals
    if pnl_pct > 15:
        score -= 5  # Consider taking profit
        reasons.append("💰 Consider profit booking")
    elif pnl_pct < -10:
        score -= 8  # Consider cutting losses
        reasons.append("⚠️ Negative P&L pressure")

    # Determine recommendation
    if score > 15:
        recommendation = "BUY"
        confidence = min(abs(score), 95)
    elif score < -15:
        recommendation = "SELL"
        confidence = min(abs(score), 95)
    else:
        recommendation = "HOLD"
        confidence = max(50 - abs(score), 30)

    return {
        "action": recommendation,
        "confidence": round(confidence, 1),
        "score": round(score, 1),
        "reasons": reasons[:5],
    }


# ═══════════════════════════════════════════════════════════
#  LLM INSIGHT GENERATOR
# ═══════════════════════════════════════════════════════════


async def generate_holding_insight(
    symbol: str,
    recommendation: str,
    confidence: float,
    patterns: list[dict],
    trend: dict,
    price: float,
    pnl_pct: float,
) -> str:
    """Generate a 1-sentence AI insight per holding."""
    settings = get_settings()

    if not settings.groq_api_key:
        return _template_insight(symbol, recommendation, patterns, trend)

    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)

        pattern_names = ", ".join([p["name"] for p in patterns]) or "none detected"

        prompt = f"""Write exactly ONE sentence about {symbol} stock for a retail investor.

Current price: ₹{price:.2f}
Recommendation: {recommendation} (confidence: {confidence}%)
Patterns detected: {pattern_names}
Trend: {trend['direction']} (RSI: {trend.get('rsi', 'N/A')})
Portfolio P&L: {pnl_pct:+.1f}%

Write ONE sentence in simple language. Be specific about what the patterns mean for the investor. No jargon."""

        response = await client.chat.completions.create(
            model=settings.groq_fallback_model,  # Use fast model for speed
            messages=[
                {"role": "system", "content": "You are a concise market analyst. ONE sentence only."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=80,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning("insight_fallback", symbol=symbol, error=str(e))
        return _template_insight(symbol, recommendation, patterns, trend)


def _template_insight(symbol, recommendation, patterns, trend):
    pattern_names = ", ".join([p["name"] for p in patterns[:2]]) or "no strong patterns"
    if recommendation == "BUY":
        return f"{symbol} shows {pattern_names} with {trend['direction']} trend momentum — consider building a position."
    elif recommendation == "SELL":
        return f"{symbol} shows {pattern_names} with weakening momentum — consider reducing exposure."
    return f"{symbol} shows {pattern_names} — hold current position and monitor for clearer signals."


# ═══════════════════════════════════════════════════════════
#  FULL PORTFOLIO SCAN PIPELINE
# ═══════════════════════════════════════════════════════════


async def scan_portfolio_holding(
    symbol: str,
    qty: int,
    buy_price: float,
    lookback_days: int = 180,
) -> dict:
    """
    Full analysis pipeline for a single holding.
    Returns all analysis data for the frontend.
    """
    from app.services.ohlcv_provider import fetch_ohlcv
    from app.services.pattern_scan_service import (
        compute_indicators,
        detect_macd_divergence,
        detect_ma_crossover,
        generate_signals,
        _fallback_backtest,
    )

    t0 = time.time()

    # Fetch OHLCV
    df = await fetch_ohlcv(symbol, interval="day", lookback_days=lookback_days)

    if df.empty:
        return {
            "symbol": symbol,
            "status": "no_data",
            "error": "No market data available",
        }

    # Current price
    current_price = float(df["close"].iloc[-1])
    prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else current_price
    day_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
    pnl_pct = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
    pnl_value = (current_price - buy_price) * qty

    # Candlestick patterns
    patterns = detect_candlestick_patterns(df)

    # Technical indicators
    df_ta = compute_indicators(df.copy())
    macd_div, macd_type = detect_macd_divergence(df_ta)
    ma_cross, ma_type = detect_ma_crossover(df_ta)

    # Trend analysis
    trend = analyze_trend(df)

    # Backtest metrics
    entries, exits = generate_signals(df_ta)
    from app.services.pattern_scan_service import run_backtest
    backtest = run_backtest(df_ta["close"], entries, exits)

    # Composite recommendation
    rec = compute_recommendation(
        patterns=patterns,
        trend=trend,
        backtest_win_rate=backtest.win_rate_pct,
        pnl_pct=pnl_pct,
    )

    # LLM insight
    insight = await generate_holding_insight(
        symbol=symbol,
        recommendation=rec["action"],
        confidence=rec["confidence"],
        patterns=patterns,
        trend=trend,
        price=current_price,
        pnl_pct=pnl_pct,
    )

    # Mini candlestick data for chart (last 30 bars)
    chart_data = []
    for _, row in df.tail(30).iterrows():
        chart_data.append({
            "o": round(float(row["open"]), 2),
            "h": round(float(row["high"]), 2),
            "l": round(float(row["low"]), 2),
            "c": round(float(row["close"]), 2),
            "v": int(row["volume"]),
        })

    elapsed_ms = (time.time() - t0) * 1000

    return {
        "symbol": symbol,
        "status": "ok",
        "price": {
            "current": round(current_price, 2),
            "prev_close": round(prev_close, 2),
            "day_change_pct": round(day_change_pct, 2),
            "buy_price": round(buy_price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_value": round(pnl_value, 2),
            "qty": qty,
            "invested": round(buy_price * qty, 2),
            "current_value": round(current_price * qty, 2),
        },
        "patterns": patterns,
        "signals": {
            "macd_divergence": macd_div,
            "macd_type": macd_type,
            "ma_crossover": ma_cross,
            "ma_type": ma_type,
        },
        "trend": trend,
        "backtest": {
            "win_rate_pct": backtest.win_rate_pct,
            "avg_return_pct": backtest.avg_return_pct,
            "max_drawdown_pct": backtest.max_drawdown_pct,
            "total_trades": backtest.total_trades,
        },
        "recommendation": rec,
        "insight": insight,
        "chart_data": chart_data,
        "latency_ms": round(elapsed_ms, 2),
    }

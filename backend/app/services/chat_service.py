"""
Chat Agent Service — LLM-powered financial assistant with tool access.

Tools available to the agent:
  - get_portfolio: Current user portfolio
  - get_stock_analysis: OHLCV + RSI/MACD + candlestick patterns for any stock
  - get_market_news: Latest news for a ticker
  - get_buy_sell_signal: Buy/sell recommendation with confidence
"""

from __future__ import annotations

import json
import time
from typing import Optional

import numpy as np
import pandas as pd

from app.config import get_settings
from app.core.observability import get_logger

logger = get_logger("services.chat_agent")

# ── Tool definitions for the LLM ──
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_analysis",
            "description": "Get technical analysis for a stock — current price, RSI, MACD, moving averages, trend, and candlestick patterns. Use this when user asks about a specific stock's condition, whether to buy/sell, or technical indicators.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE stock symbol (e.g. RELIANCE, TCS, INFY)"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_summary",
            "description": "Get the user's current portfolio holdings with P&L, allocation, and overall status. Use when user asks about their portfolio, holdings, or overall performance.",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_news",
            "description": "Get the latest market news for a specific stock or general market. Use when user asks about news, events, or recent developments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker to get news for (e.g. TCS, RELIANCE). Leave empty for general market news."
                    }
                },
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_buy_sell_signal",
            "description": "Get a buy/sell/hold recommendation for a specific stock based on technical analysis including candlestick patterns, MACD, RSI, and moving averages. Use when user explicitly asks for buy/sell advice or recommendation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "NSE stock symbol (e.g. RELIANCE, TCS)"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
]

SYSTEM_PROMPT = """You are Alpha-Hunter AI, an expert Indian stock market assistant. You help users understand their portfolio, analyze stocks, interpret candlestick patterns, and make informed investment decisions.

Key behaviors:
- Always be specific with numbers, percentages, and data
- Explain technical indicators in simple terms
- When giving buy/sell signals, always mention the confidence level and reasoning
- Reference candlestick patterns by name and explain what they mean
- Format responses with clear structure using bullet points
- If you don't have data, say so honestly
- Always mention that this is for educational purposes and not financial advice
- Keep responses concise but informative (3-5 paragraphs max)
- Use ₹ for Indian Rupee values

You have access to real portfolio data, live stock analysis, market news, and candlestick pattern detection."""


# ═══════════════════════════════════════════════════════════
#  Tool Implementations
# ═══════════════════════════════════════════════════════════

async def _tool_get_stock_analysis(symbol: str) -> dict:
    """Fetch OHLCV data and run technical analysis."""
    from app.services.ohlcv_provider import fetch_ohlcv
    from app.services.candlestick_agent import detect_candlestick_patterns

    df = await fetch_ohlcv(symbol, interval="day", lookback_days=90)
    if df.empty:
        return {"symbol": symbol, "error": "No market data available. Check if the symbol is correct."}

    # Current price
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    price = float(latest["close"])
    day_change = float(latest["close"] - prev["close"])
    day_change_pct = (day_change / prev["close"] * 100) if prev["close"] else 0

    # RSI (14 period)
    close = df["close"]
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50.0

    # MACD (12, 26, 9)
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    macd_data = {
        "macd": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "histogram": float(histogram.iloc[-1]),
        "divergence": "none"  # Simplified
    }

    # Moving averages
    sma_20 = float(close.rolling(20).mean().iloc[-1])
    sma_50 = float(close.rolling(50).mean().iloc[-1]) if len(df) >= 50 else 0.0
    ma_data = {
        "sma_20": sma_20,
        "sma_50": sma_50,
        "ema_12": float(ema_12.iloc[-1])
    }

    # Trend
    if price > sma_20 and (sma_50 == 0 or sma_20 > sma_50):
        trend = "uptrend"
    elif price < sma_20 and (sma_50 == 0 or sma_20 < sma_50):
        trend = "downtrend"
    else:
        trend = "sideways"

    # Candlestick patterns
    patterns = detect_candlestick_patterns(df)

    # Volume analysis
    avg_vol = float(df["volume"].tail(20).mean()) if "volume" in df.columns else 0
    curr_vol = float(latest["volume"]) if "volume" in df.columns else 0
    vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 1

    return {
        "symbol": symbol,
        "current_price": round(price, 2),
        "day_change": round(day_change, 2),
        "day_change_pct": round(day_change_pct, 2),
        "rsi": round(rsi, 1),
        "rsi_signal": "Oversold (Buy Zone)" if rsi < 30 else "Overbought (Sell Zone)" if rsi > 70 else "Neutral",
        "macd_value": round(macd_data.get("macd", 0), 4),
        "macd_signal": round(macd_data.get("signal", 0), 4),
        "macd_histogram": round(macd_data.get("histogram", 0), 4),
        "macd_divergence": macd_data.get("divergence", "none"),
        "sma_20": round(ma_data.get("sma_20", 0), 2),
        "sma_50": round(ma_data.get("sma_50", 0), 2),
        "ema_12": round(ma_data.get("ema_12", 0), 2),
        "price_vs_sma20": "Above" if price > ma_data.get("sma_20", 0) else "Below",
        "trend": trend,
        "candlestick_patterns": [
            {"name": p["name"], "type": p["type"], "signal": p["signal"], "confidence": p.get("confidence", 0)}
            for p in patterns
        ] if patterns else [],
        "volume_current": int(curr_vol),
        "volume_avg_20d": int(avg_vol),
        "volume_ratio": round(vol_ratio, 2),
        "volume_signal": "High Volume" if vol_ratio > 1.5 else "Low Volume" if vol_ratio < 0.5 else "Normal",
        "52w_high": round(float(df["high"].max()), 2),
        "52w_low": round(float(df["low"].min()), 2),
    }


async def _tool_get_portfolio_summary(holdings: list[dict]) -> dict:
    """Summarize user portfolio."""
    if not holdings:
        return {"error": "No portfolio holdings found. Add stocks first."}

    from app.services.ohlcv_provider import fetch_ohlcv

    results = []
    total_invested = 0
    total_current = 0

    for h in holdings[:10]:  # Max 10
        sym = h.get("symbol", h.get("ticker", ""))
        qty = h.get("qty", h.get("quantity", 0))
        buy_price = h.get("buy_price", h.get("buyPrice", 0))

        if not sym or qty <= 0:
            continue

        # Try to get current price
        current_price = buy_price
        try:
            df = await fetch_ohlcv(sym, interval="day", lookback_days=5)
            if not df.empty:
                current_price = float(df.iloc[-1]["close"])
        except Exception:
            pass

        invested = buy_price * qty
        current = current_price * qty
        pnl = current - invested
        pnl_pct = (pnl / invested * 100) if invested else 0

        total_invested += invested
        total_current += current

        results.append({
            "symbol": sym,
            "qty": qty,
            "buy_price": round(buy_price, 2),
            "current_price": round(current_price, 2),
            "invested": round(invested, 2),
            "current_value": round(current, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

    return {
        "holdings_count": len(results),
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "holdings": results,
    }


async def _tool_get_market_news(ticker: str = "") -> dict:
    """Get mock market news for a ticker."""
    import random
    from datetime import datetime, timedelta

    templates = [
        (f"{ticker or 'Market'} shows strong momentum as institutional buying continues", "bullish"),
        (f"Analysts upgrade {ticker or 'Nifty'} target on improving fundamentals", "bullish"),
        (f"{ticker or 'Market'} faces selling pressure amid global uncertainty", "bearish"),
        (f"{ticker or 'Sensex'} consolidates near key support levels", "neutral"),
        (f"FII flows into {ticker or 'Indian markets'} turn positive this week", "bullish"),
        (f"{ticker or 'Market'} sector rotation benefits value stocks", "neutral"),
        (f"{ticker or 'Nifty'} technical outlook: key resistance at upper Bollinger band", "neutral"),
        (f"Domestic funds increase exposure to {ticker or 'large-cap stocks'}", "bullish"),
    ]

    selected = random.sample(templates, min(4, len(templates)))
    now = datetime.utcnow()

    return {
        "ticker": ticker or "General Market",
        "news": [
            {
                "headline": t[0],
                "sentiment": t[1],
                "time": (now - timedelta(hours=random.randint(1, 48))).isoformat() + "Z",
                "source": random.choice(["Economic Times", "Moneycontrol", "LiveMint", "Business Standard"]),
            }
            for t in selected
        ],
    }


async def _tool_get_buy_sell_signal(symbol: str) -> dict:
    """Generate buy/sell recommendation based on full technical analysis."""
    analysis = await _tool_get_stock_analysis(symbol)

    if "error" in analysis:
        return analysis

    # Scoring system
    score = 0
    reasons = []

    # RSI
    rsi = analysis.get("rsi", 50)
    if rsi < 30:
        score += 2
        reasons.append(f"RSI at {rsi:.0f} — oversold, potential bounce")
    elif rsi < 40:
        score += 1
        reasons.append(f"RSI at {rsi:.0f} — approaching oversold")
    elif rsi > 70:
        score -= 2
        reasons.append(f"RSI at {rsi:.0f} — overbought, potential pullback")
    elif rsi > 60:
        score -= 1
        reasons.append(f"RSI at {rsi:.0f} — approaching overbought")
    else:
        reasons.append(f"RSI at {rsi:.0f} — neutral zone")

    # MACD
    hist = analysis.get("macd_histogram", 0)
    if hist > 0:
        score += 1
        reasons.append("MACD histogram positive — bullish momentum")
    elif hist < 0:
        score -= 1
        reasons.append("MACD histogram negative — bearish momentum")

    div = analysis.get("macd_divergence", "none")
    if "bullish" in div.lower():
        score += 2
        reasons.append(f"MACD bullish divergence detected — strong buy signal")
    elif "bearish" in div.lower():
        score -= 2
        reasons.append(f"MACD bearish divergence — caution")

    # Price vs MA
    if analysis.get("price_vs_sma20") == "Above":
        score += 1
        reasons.append("Price above 20-SMA — short-term uptrend")
    else:
        score -= 1
        reasons.append("Price below 20-SMA — short-term weakness")

    # Trend
    trend = analysis.get("trend", "sideways")
    if trend == "uptrend":
        score += 1
        reasons.append("Overall trend is bullish")
    elif trend == "downtrend":
        score -= 1
        reasons.append("Overall trend is bearish")

    # Candlestick patterns
    patterns = analysis.get("candlestick_patterns", [])
    for p in patterns:
        if p.get("signal") == "bullish":
            score += 1
            reasons.append(f"Bullish pattern: {p['name']}")
        elif p.get("signal") == "bearish":
            score -= 1
            reasons.append(f"Bearish pattern: {p['name']}")

    # Volume
    vol_sig = analysis.get("volume_signal", "")
    if vol_sig == "High Volume":
        reasons.append("High volume confirms current move")

    # Decision
    if score >= 3:
        decision = "STRONG BUY"
        confidence = min(90, 60 + score * 5)
    elif score >= 1:
        decision = "BUY"
        confidence = min(75, 50 + score * 5)
    elif score <= -3:
        decision = "STRONG SELL"
        confidence = min(90, 60 + abs(score) * 5)
    elif score <= -1:
        decision = "SELL"
        confidence = min(75, 50 + abs(score) * 5)
    else:
        decision = "HOLD"
        confidence = 50

    return {
        "symbol": symbol,
        "decision": decision,
        "confidence": confidence,
        "score": score,
        "current_price": analysis.get("current_price"),
        "rsi": analysis.get("rsi"),
        "trend": analysis.get("trend"),
        "reasons": reasons,
        "candlestick_patterns": patterns,
        "disclaimer": "This is for educational purposes only. Not financial advice.",
    }


# ═══════════════════════════════════════════════════════════
#  Main Chat Function
# ═══════════════════════════════════════════════════════════

async def process_chat(
    message: str,
    history: list[dict],
    portfolio: list[dict],
) -> str:
    """Process a chat message with tool-calling support."""
    settings = get_settings()
    t0 = time.time()

    if not settings.groq_api_key:
        return "⚠️ LLM API key not configured. Please set GROQ_API_KEY in your .env file."

    try:
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)

        # Build messages
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add portfolio context
        if portfolio:
            symbols = [h.get("symbol", h.get("ticker", "")) for h in portfolio[:10]]
            messages[0]["content"] += f"\n\nUser's portfolio contains: {', '.join(symbols)} ({len(portfolio)} stocks total)"

        # Add conversation history (last 10 messages)
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Current user message
        messages.append({"role": "user", "content": message})

        # First call — may request tools
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            max_tokens=1024,
            temperature=0.3,
        )

        choice = response.choices[0]

        # If no tool calls, return directly
        if not choice.message.tool_calls:
            return choice.message.content or "I couldn't generate a response. Please try again."

        # Execute tool calls
        messages.append(choice.message)  # Add assistant message with tool calls

        for tool_call in choice.message.tool_calls:
            fn_name = tool_call.function.name
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                args = {}

            logger.info("chat_tool_call", function=fn_name, args=args)

            # Execute the appropriate tool
            if fn_name == "get_stock_analysis":
                result = await _tool_get_stock_analysis(args.get("symbol", ""))
            elif fn_name == "get_portfolio_summary":
                result = await _tool_get_portfolio_summary(portfolio)
            elif fn_name == "get_market_news":
                result = await _tool_get_market_news(args.get("ticker", ""))
            elif fn_name == "get_buy_sell_signal":
                result = await _tool_get_buy_sell_signal(args.get("symbol", ""))
            else:
                result = {"error": f"Unknown tool: {fn_name}"}

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })

        # Second call — with tool results
        final_response = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            max_tokens=1024,
            temperature=0.3,
        )

        answer = final_response.choices[0].message.content or ""
        elapsed = time.time() - t0
        logger.info("chat_completed", elapsed=round(elapsed, 2), tools_called=len(choice.message.tool_calls))
        return answer

    except Exception as e:
        logger.error("chat_error", error=str(e))
        return f"❌ Error: {str(e)}\n\nPlease try again or rephrase your question."

"""
Intelligence Service — AI-powered portfolio analysis across 3 categories.

Category 1: Portfolio Health — condition, P&L, risk, diversification
Category 2: Market Analysis — technical signals, patterns, momentum
Category 3: Historical Performance — seasonality, volatility, backtests

All functions accept a list of holdings and return structured reports.
Reuses existing services: ohlcv_provider, pattern_scan_service, candlestick_agent.
"""

from __future__ import annotations

import asyncio
import time
import math
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd

from app.config import get_settings
from app.core.observability import get_logger
from app.schemas.intelligence import (
    HoldingInput, HoldingHealth, PortfolioHealthReport,
    HoldingSignal, MarketAnalysisReport,
    HoldingHistorical, HistoricalReport,
    MonthlyReturn, DayOfWeekReturn,
)

logger = get_logger("services.intelligence")

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ═══════════════════════════════════════════════════════════
#  SHARED: Fetch OHLCV for multiple holdings concurrently
# ═══════════════════════════════════════════════════════════


async def _fetch_all_ohlcv(holdings: List[HoldingInput], lookback: int = 365) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV data for all holdings concurrently, capped at 5 parallel."""
    from app.services.ohlcv_provider import fetch_ohlcv

    sem = asyncio.Semaphore(5)
    results: dict[str, pd.DataFrame] = {}

    async def _fetch_one(h: HoldingInput):
        async with sem:
            try:
                df = await fetch_ohlcv(h.symbol.upper(), interval="day", lookback_days=lookback)
                results[h.symbol.upper()] = df
            except Exception as e:
                logger.warning("intel_ohlcv_error", symbol=h.symbol, error=str(e))
                results[h.symbol.upper()] = pd.DataFrame()

    await asyncio.gather(*[_fetch_one(h) for h in holdings])
    return results


async def _llm_summarize(prompt: str) -> str:
    """Generate a short LLM summary via Groq."""
    settings = get_settings()
    if not settings.groq_api_key:
        return ""
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key)
        resp = await client.chat.completions.create(
            model=settings.groq_fallback_model,
            messages=[
                {"role": "system", "content": "You are a portfolio analyst writing short, actionable summaries for retail investors. 3-4 sentences max. No jargon. Use ₹ for INR."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=250,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("intel_llm_error", error=str(e))
        return ""


def _compute_rsi(close: pd.Series, period: int = 14) -> float:
    """Compute latest RSI value."""
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val), 1) if not np.isnan(val) else 50.0


def _compute_trend(close: pd.Series) -> str:
    """Determine trend direction from SMA."""
    if len(close) < 20:
        return "neutral"
    sma_20 = close.rolling(20).mean().iloc[-1]
    current = close.iloc[-1]
    if current > sma_20 * 1.02:
        return "bullish"
    elif current < sma_20 * 0.98:
        return "bearish"
    return "neutral"


# ═══════════════════════════════════════════════════════════
#  CATEGORY 1: Portfolio Health Report
# ═══════════════════════════════════════════════════════════


async def generate_portfolio_health(holdings: List[HoldingInput]) -> PortfolioHealthReport:
    """Generate comprehensive portfolio health assessment."""
    t0 = time.time()

    data = await _fetch_all_ohlcv(holdings, lookback=90)

    holding_results: List[HoldingHealth] = []
    total_invested = 0.0
    total_current = 0.0

    for h in holdings:
        sym = h.symbol.upper()
        df = data.get(sym, pd.DataFrame())

        if df.empty:
            holding_results.append(HoldingHealth(
                symbol=sym, buy_price=h.buy_price, qty=h.qty,
                health_status="critical",
            ))
            continue

        current_price = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else current_price
        invested = h.buy_price * h.qty
        current_value = current_price * h.qty
        pnl_value = current_value - invested
        pnl_pct = (pnl_value / invested * 100) if invested > 0 else 0
        day_change = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0

        rsi = _compute_rsi(df["close"])
        trend = _compute_trend(df["close"])

        # Health classification
        if pnl_pct >= 5 and rsi < 70 and trend != "bearish":
            status = "healthy"
        elif pnl_pct < -10 or rsi > 80 or rsi < 20:
            status = "critical"
        elif pnl_pct < -5 or trend == "bearish":
            status = "warning"
        else:
            status = "healthy"

        total_invested += invested
        total_current += current_value

        holding_results.append(HoldingHealth(
            symbol=sym,
            current_price=round(current_price, 2),
            buy_price=round(h.buy_price, 2),
            qty=h.qty,
            invested=round(invested, 2),
            current_value=round(current_value, 2),
            pnl_value=round(pnl_value, 2),
            pnl_pct=round(pnl_pct, 2),
            day_change_pct=round(day_change, 2),
            rsi=rsi,
            trend=trend,
            health_status=status,
        ))

    # Compute weight percentages
    for hh in holding_results:
        if total_current > 0:
            hh.weight_pct = round(hh.current_value / total_current * 100, 1)

    # Aggregate
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0

    # Best/worst
    ok_holdings = [h for h in holding_results if h.current_price > 0]
    best = max(ok_holdings, key=lambda x: x.pnl_pct) if ok_holdings else None
    worst = min(ok_holdings, key=lambda x: x.pnl_pct) if ok_holdings else None

    # Concentration
    max_wt = max((h.weight_pct for h in holding_results), default=0)
    max_wt_sym = next((h.symbol for h in holding_results if h.weight_pct == max_wt), None)

    # Diversification score: HHI-based (lower HHI = more diversified)
    weights = [h.weight_pct / 100 for h in holding_results if h.weight_pct > 0]
    hhi = sum(w * w for w in weights)
    # Perfect diversification among N stocks → HHI = 1/N
    ideal_hhi = 1 / max(len(weights), 1)
    div_score = max(0, min(100, (1 - hhi) / (1 - ideal_hhi) * 100)) if len(weights) > 1 else 0

    healthy = sum(1 for h in holding_results if h.health_status == "healthy")
    warning = sum(1 for h in holding_results if h.health_status == "warning")
    critical = sum(1 for h in holding_results if h.health_status == "critical")

    # LLM summary
    summary_prompt = f"""Analyze this portfolio's health in 3-4 sentences:

Total Invested: ₹{total_invested:,.0f}
Current Value: ₹{total_current:,.0f}  
Overall P&L: ₹{total_pnl:,.0f} ({total_pnl_pct:+.1f}%)
Holdings: {len(holdings)} stocks
Healthy: {healthy}, Warning: {warning}, Critical: {critical}
Best: {best.symbol if best else 'N/A'} ({best.pnl_pct:+.1f}% P&L) if best else ''
Worst: {worst.symbol if worst else 'N/A'} ({worst.pnl_pct:+.1f}% P&L) if worst else ''
Max Concentration: {max_wt_sym} at {max_wt:.0f}%
Diversification Score: {div_score:.0f}/100

Give actionable insights. Mention specific stocks. Be honest about risks."""

    ai_summary = await _llm_summarize(summary_prompt)

    elapsed = (time.time() - t0) * 1000

    return PortfolioHealthReport(
        total_invested=round(total_invested, 2),
        total_current_value=round(total_current, 2),
        total_pnl_value=round(total_pnl, 2),
        total_pnl_pct=round(total_pnl_pct, 2),
        holdings_count=len(holdings),
        best_performer=best.symbol if best else None,
        best_performer_pnl_pct=round(best.pnl_pct, 2) if best else 0,
        worst_performer=worst.symbol if worst else None,
        worst_performer_pnl_pct=round(worst.pnl_pct, 2) if worst else 0,
        max_concentration_pct=round(max_wt, 1),
        max_concentration_symbol=max_wt_sym,
        diversification_score=round(div_score, 1),
        healthy_count=healthy,
        warning_count=warning,
        critical_count=critical,
        holdings=holding_results,
        ai_summary=ai_summary,
        latency_ms=round(elapsed, 2),
    )


# ═══════════════════════════════════════════════════════════
#  CATEGORY 2: Market Analysis Report
# ═══════════════════════════════════════════════════════════


async def generate_market_analysis(holdings: List[HoldingInput]) -> MarketAnalysisReport:
    """Generate market signal analysis for all holdings."""
    t0 = time.time()

    data = await _fetch_all_ohlcv(holdings, lookback=365)

    from app.services.pattern_scan_service import (
        compute_indicators, detect_macd_divergence, detect_ma_crossover,
    )
    from app.services.candlestick_agent import detect_candlestick_patterns, analyze_trend

    holding_signals: List[HoldingSignal] = []
    active_patterns: List[str] = []
    active_divergences: List[str] = []
    active_crossovers: List[str] = []

    for h in holdings:
        sym = h.symbol.upper()
        df = data.get(sym, pd.DataFrame())

        if df.empty:
            holding_signals.append(HoldingSignal(symbol=sym))
            continue

        current_price = float(df["close"].iloc[-1])
        prev_close = float(df["close"].iloc[-2]) if len(df) > 1 else current_price
        day_change = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0

        # Technical indicators
        df_ta = compute_indicators(df.copy())
        macd_div, macd_type = detect_macd_divergence(df_ta)
        ma_cross, ma_type = detect_ma_crossover(df_ta)

        # Candlestick patterns
        patterns = detect_candlestick_patterns(df)
        pattern_names = [p["name"] for p in patterns]
        pattern_signals = [p["signal"] for p in patterns]

        # Trend
        trend_info = analyze_trend(df)
        rsi = trend_info.get("rsi", 50)

        # Compute signal strength score
        score = 0
        bullish_patterns = [p for p in patterns if p["signal"] == "bullish"]
        bearish_patterns = [p for p in patterns if p["signal"] == "bearish"]
        score += len(bullish_patterns) * 15
        score -= len(bearish_patterns) * 15
        if macd_div:
            score += 20 if macd_type == "bullish" else -20
        if ma_cross:
            score += 25 if ma_type == "golden_cross" else -25
        if trend_info["direction"] == "bullish":
            score += 10
        elif trend_info["direction"] == "bearish":
            score -= 10
        if rsi < 30:
            score += 15  # oversold
        elif rsi > 70:
            score -= 15  # overbought

        if score > 30:
            strength = "strong_buy"
        elif score > 10:
            strength = "buy"
        elif score < -30:
            strength = "strong_sell"
        elif score < -10:
            strength = "sell"
        else:
            strength = "neutral"

        # Collect active signals
        for p in patterns:
            active_patterns.append(f"{sym}: {p['emoji']} {p['name']} ({p['signal']})")
        if macd_div:
            active_divergences.append(f"{sym}: MACD {macd_type} divergence")
        if ma_cross:
            label = "Golden Cross ↑" if ma_type == "golden_cross" else "Death Cross ↓"
            active_crossovers.append(f"{sym}: {label}")

        holding_signals.append(HoldingSignal(
            symbol=sym,
            current_price=round(current_price, 2),
            day_change_pct=round(day_change, 2),
            trend=trend_info["direction"],
            rsi=round(rsi, 1),
            macd_divergence=macd_div,
            macd_type=macd_type,
            ma_crossover=ma_cross,
            ma_type=ma_type,
            candlestick_patterns=pattern_names,
            pattern_signals=pattern_signals,
            signal_strength=strength,
            signal_score=round(score, 1),
        ))

    # Aggregate
    strengths = [h.signal_strength for h in holding_signals]
    sb = strengths.count("strong_buy")
    b = strengths.count("buy")
    n = strengths.count("neutral")
    s = strengths.count("sell")
    ss = strengths.count("strong_sell")

    rsi_vals = [h.rsi for h in holding_signals if h.current_price > 0]
    avg_rsi = sum(rsi_vals) / len(rsi_vals) if rsi_vals else 50

    trends = [h.trend for h in holding_signals if h.current_price > 0]
    bullish_pct = (trends.count("bullish") / len(trends) * 100) if trends else 0
    bearish_pct = (trends.count("bearish") / len(trends) * 100) if trends else 0

    # LLM summary
    summary_prompt = f"""Analyze the market conditions for this portfolio in 3-4 sentences:

Holdings analyzed: {len(holdings)}
Signal breakdown: {sb} Strong Buy, {b} Buy, {n} Neutral, {s} Sell, {ss} Strong Sell
Average RSI: {avg_rsi:.0f}
Bullish holdings: {bullish_pct:.0f}%, Bearish: {bearish_pct:.0f}%
Active patterns: {'; '.join(active_patterns[:5]) or 'None'}
Active divergences: {'; '.join(active_divergences) or 'None'}
Active crossovers: {'; '.join(active_crossovers) or 'None'}

Tell the investor what the market signals mean for their portfolio today. Be specific about which stocks show the strongest signals."""

    ai_summary = await _llm_summarize(summary_prompt)
    elapsed = (time.time() - t0) * 1000

    return MarketAnalysisReport(
        strong_buy_count=sb,
        buy_count=b,
        neutral_count=n,
        sell_count=s,
        strong_sell_count=ss,
        avg_rsi=round(avg_rsi, 1),
        bullish_pct=round(bullish_pct, 1),
        bearish_pct=round(bearish_pct, 1),
        active_patterns=active_patterns[:10],
        active_divergences=active_divergences,
        active_crossovers=active_crossovers,
        holdings=holding_signals,
        ai_summary=ai_summary,
        latency_ms=round(elapsed, 2),
    )


# ═══════════════════════════════════════════════════════════
#  CATEGORY 3: Historical Performance Report
# ═══════════════════════════════════════════════════════════


async def generate_historical_report(holdings: List[HoldingInput]) -> HistoricalReport:
    """Generate historical performance analysis for the portfolio."""
    t0 = time.time()

    # Fetch 2 years of data for seasonality
    data = await _fetch_all_ohlcv(holdings, lookback=730)

    from app.services.pattern_scan_service import (
        compute_indicators, generate_signals, _fallback_backtest,
    )

    holding_results: List[HoldingHistorical] = []
    all_monthly: dict[int, list] = {m: [] for m in range(1, 13)}
    all_daily: dict[int, list] = {d: [] for d in range(5)}  # Mon-Fri
    vol_vals = []

    now = datetime.now()
    current_month = now.month

    for h in holdings:
        sym = h.symbol.upper()
        df = data.get(sym, pd.DataFrame())

        if df.empty:
            holding_results.append(HoldingHistorical(symbol=sym))
            continue

        close = df["close"]
        returns = close.pct_change().dropna() * 100

        # -- Backtest --
        df_ta = compute_indicators(df.copy())
        entries, exits = generate_signals(df_ta)
        bt = _fallback_backtest(df_ta["close"], entries, exits)

        # -- Volatility --
        recent_vol = returns.iloc[-30:].std() * math.sqrt(252) if len(returns) >= 30 else 0
        hist_vol = returns.std() * math.sqrt(252) if len(returns) > 30 else recent_vol

        if recent_vol > hist_vol * 1.5:
            vol_regime = "high"
        elif recent_vol > hist_vol * 2.0:
            vol_regime = "extreme"
        elif recent_vol < hist_vol * 0.6:
            vol_regime = "low"
        else:
            vol_regime = "normal"

        vol_vals.append(recent_vol)

        # -- YTD return --
        jan1 = pd.Timestamp(year=now.year, month=1, day=1, tz=close.index.tz if close.index.tz else None)
        ytd_df = close[close.index >= jan1]
        ytd_return = ((ytd_df.iloc[-1] / ytd_df.iloc[0] - 1) * 100) if len(ytd_df) > 1 else 0

        # -- 1Y return --
        one_yr_ago = close.index[-1] - pd.Timedelta(days=365)
        yr_df = close[close.index >= one_yr_ago]
        one_yr_return = ((yr_df.iloc[-1] / yr_df.iloc[0] - 1) * 100) if len(yr_df) > 1 else 0

        # -- Monthly seasonality --
        if hasattr(df.index, 'month'):
            monthly_returns = returns.groupby(returns.index.month)
            for month_num, group in monthly_returns:
                avg_r = group.mean()
                win_r = (group > 0).mean() * 100
                all_monthly[month_num].append(avg_r)

            cur_month_data = monthly_returns.get_group(current_month) if current_month in monthly_returns.groups else pd.Series()
            cur_month_avg = cur_month_data.mean() if len(cur_month_data) > 0 else 0
            cur_month_win = (cur_month_data > 0).mean() * 100 if len(cur_month_data) > 0 else 0
        else:
            cur_month_avg = 0
            cur_month_win = 0

        # -- Day of week --
        if hasattr(df.index, 'dayofweek'):
            dow_returns = returns.groupby(returns.index.dayofweek)
            for day_num, group in dow_returns:
                if day_num < 5:  # Weekdays only
                    all_daily[day_num].append(group.mean())

        holding_results.append(HoldingHistorical(
            symbol=sym,
            backtest_win_rate=bt.win_rate_pct,
            backtest_avg_return=bt.avg_return_pct,
            backtest_max_drawdown=bt.max_drawdown_pct,
            backtest_total_trades=bt.total_trades,
            current_volatility=round(float(recent_vol), 2),
            historical_avg_volatility=round(float(hist_vol), 2),
            vol_regime=vol_regime,
            ytd_return_pct=round(float(ytd_return), 2),
            one_year_return_pct=round(float(one_yr_return), 2),
            current_month_avg_return=round(float(cur_month_avg), 4),
            current_month_win_rate=round(float(cur_month_win), 1),
        ))

    # Portfolio-level aggregates
    ytd_vals = [h.ytd_return_pct for h in holding_results if h.ytd_return_pct != 0]
    yr_vals = [h.one_year_return_pct for h in holding_results if h.one_year_return_pct != 0]
    port_ytd = sum(ytd_vals) / len(ytd_vals) if ytd_vals else 0
    port_1y = sum(yr_vals) / len(yr_vals) if yr_vals else 0
    avg_vol = sum(vol_vals) / len(vol_vals) if vol_vals else 0

    vol_regimes = [h.vol_regime for h in holding_results]
    if vol_regimes.count("extreme") > 0:
        port_vol_regime = "extreme"
    elif vol_regimes.count("high") > len(vol_regimes) / 2:
        port_vol_regime = "high"
    elif vol_regimes.count("low") > len(vol_regimes) / 2:
        port_vol_regime = "low"
    else:
        port_vol_regime = "normal"

    # Monthly seasonality (portfolio average)
    monthly_season = []
    for m in range(1, 13):
        vals = all_monthly[m]
        avg_r = sum(vals) / len(vals) if vals else 0
        win_r = (sum(1 for v in vals if v > 0) / len(vals) * 100) if vals else 0
        monthly_season.append(MonthlyReturn(
            month=m, month_name=MONTH_NAMES[m],
            avg_return_pct=round(avg_r, 4),
            win_rate_pct=round(win_r, 1),
            data_years=len(vals),
        ))

    cur_m = monthly_season[current_month - 1]
    cur_outlook = "favorable" if cur_m.avg_return_pct > 0.05 else "unfavorable" if cur_m.avg_return_pct < -0.05 else "neutral"

    # Day-of-week
    dow_results = []
    for d in range(5):
        vals = all_daily[d]
        avg_r = sum(vals) / len(vals) if vals else 0
        pos_pct = (sum(1 for v in vals if v > 0) / len(vals) * 100) if vals else 0
        dow_results.append(DayOfWeekReturn(
            day=d, day_name=DAY_NAMES[d],
            avg_return_pct=round(avg_r, 4),
            positive_pct=round(pos_pct, 1),
        ))

    best_dow = max(dow_results, key=lambda x: x.avg_return_pct) if dow_results else None
    worst_dow = min(dow_results, key=lambda x: x.avg_return_pct) if dow_results else None

    # Backtest averages
    bt_wins = [h.backtest_win_rate for h in holding_results if h.backtest_total_trades > 0]
    bt_dds = [h.backtest_max_drawdown for h in holding_results if h.backtest_total_trades > 0]
    avg_win = sum(bt_wins) / len(bt_wins) if bt_wins else 0
    avg_dd = sum(bt_dds) / len(bt_dds) if bt_dds else 0

    # LLM summary
    summary_prompt = f"""Analyze historical performance patterns for this portfolio in 3-4 sentences:

Portfolio YTD return: {port_ytd:+.1f}%
Portfolio 1-year return: {port_1y:+.1f}%
Current volatility regime: {port_vol_regime}
Average portfolio volatility: {avg_vol:.1f}%

Current month ({MONTH_NAMES[current_month]}): avg return {cur_m.avg_return_pct:+.4f}%, win rate {cur_m.win_rate_pct:.0f}%
Best weekday: {best_dow.day_name if best_dow else 'N/A'} ({best_dow.avg_return_pct:+.4f}%)
Worst weekday: {worst_dow.day_name if worst_dow else 'N/A'} ({worst_dow.avg_return_pct:+.4f}%)

Average backtest win rate: {avg_win:.1f}%
Average max drawdown: {avg_dd:.1f}%

Tell the investor what historical patterns suggest about their portfolio's behavior.
Mention the current month's seasonality and volatility regime. Be specific."""

    ai_summary = await _llm_summarize(summary_prompt)
    elapsed = (time.time() - t0) * 1000

    return HistoricalReport(
        portfolio_ytd_return_pct=round(port_ytd, 2),
        portfolio_1y_return_pct=round(port_1y, 2),
        avg_portfolio_volatility=round(avg_vol, 2),
        vol_regime=port_vol_regime,
        current_month=MONTH_NAMES[current_month],
        current_month_avg_return=round(cur_m.avg_return_pct, 4),
        current_month_win_rate=round(cur_m.win_rate_pct, 1),
        current_month_outlook=cur_outlook,
        best_weekday=best_dow.day_name if best_dow else None,
        best_weekday_return=round(best_dow.avg_return_pct, 4) if best_dow else 0,
        worst_weekday=worst_dow.day_name if worst_dow else None,
        worst_weekday_return=round(worst_dow.avg_return_pct, 4) if worst_dow else 0,
        portfolio_avg_win_rate=round(avg_win, 1),
        portfolio_avg_drawdown=round(avg_dd, 1),
        holdings=holding_results,
        monthly_seasonality=monthly_season,
        day_of_week_returns=dow_results,
        ai_summary=ai_summary,
        latency_ms=round(elapsed, 2),
    )

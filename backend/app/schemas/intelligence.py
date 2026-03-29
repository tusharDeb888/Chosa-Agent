"""
Intelligence Report Schemas — Typed models for the 3-category AI Portfolio Intelligence Agent.

Category 1: Portfolio Health Report — portfolio condition, P&L, diversification, risk
Category 2: Market Analysis Report — technical signals, candlestick patterns, sector momentum
Category 3: Historical Performance Report — seasonality, volatility, backtest summaries
"""

from __future__ import annotations

from typing import Optional, List
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
#  Shared Request
# ═══════════════════════════════════════════════════════════


class HoldingInput(BaseModel):
    """Single holding in the user's portfolio."""
    symbol: str
    qty: int = 0
    buy_price: float = 0.0


class IntelligenceRequest(BaseModel):
    """Shared request body for all 3 intelligence endpoints."""
    holdings: List[HoldingInput] = Field(..., min_length=1)


# ═══════════════════════════════════════════════════════════
#  Category 1: Portfolio Health Report
# ═══════════════════════════════════════════════════════════


class HoldingHealth(BaseModel):
    """Health status for a single holding."""
    symbol: str
    current_price: float = 0.0
    buy_price: float = 0.0
    qty: int = 0
    invested: float = 0.0
    current_value: float = 0.0
    pnl_value: float = 0.0
    pnl_pct: float = 0.0
    day_change_pct: float = 0.0
    rsi: float = 50.0
    trend: str = "neutral"  # bullish | bearish | neutral
    health_status: str = "neutral"  # healthy | warning | critical
    weight_pct: float = 0.0  # % of total portfolio value


class PortfolioHealthReport(BaseModel):
    """Full portfolio health assessment."""
    # Aggregate metrics
    total_invested: float = 0.0
    total_current_value: float = 0.0
    total_pnl_value: float = 0.0
    total_pnl_pct: float = 0.0
    holdings_count: int = 0

    # Risk indicators
    best_performer: Optional[str] = None
    best_performer_pnl_pct: float = 0.0
    worst_performer: Optional[str] = None
    worst_performer_pnl_pct: float = 0.0
    max_concentration_pct: float = 0.0
    max_concentration_symbol: Optional[str] = None
    diversification_score: float = 0.0  # 0-100, higher = more diversified

    # Health counts
    healthy_count: int = 0
    warning_count: int = 0
    critical_count: int = 0

    # Per-holding detail
    holdings: List[HoldingHealth] = []

    # AI narrative
    ai_summary: str = ""
    latency_ms: float = 0.0


# ═══════════════════════════════════════════════════════════
#  Category 2: Market Analysis Report
# ═══════════════════════════════════════════════════════════


class HoldingSignal(BaseModel):
    """Technical signal for a single holding."""
    symbol: str
    current_price: float = 0.0
    day_change_pct: float = 0.0
    trend: str = "neutral"
    rsi: float = 50.0
    macd_divergence: bool = False
    macd_type: Optional[str] = None
    ma_crossover: bool = False
    ma_type: Optional[str] = None
    candlestick_patterns: List[str] = []
    pattern_signals: List[str] = []  # bullish/bearish/neutral per pattern
    signal_strength: str = "neutral"  # strong_buy | buy | neutral | sell | strong_sell
    signal_score: float = 0.0


class MarketAnalysisReport(BaseModel):
    """Market analysis across all portfolio holdings."""
    # Aggregate signals
    strong_buy_count: int = 0
    buy_count: int = 0
    neutral_count: int = 0
    sell_count: int = 0
    strong_sell_count: int = 0

    # Portfolio momentum
    avg_rsi: float = 50.0
    bullish_pct: float = 0.0  # % of holdings in bullish trend
    bearish_pct: float = 0.0

    # Active signals
    active_patterns: List[str] = []  # e.g. ["RELIANCE: Hammer (bullish)", ...]
    active_divergences: List[str] = []
    active_crossovers: List[str] = []

    # Per-holding detail
    holdings: List[HoldingSignal] = []

    # AI narrative
    ai_summary: str = ""
    latency_ms: float = 0.0


# ═══════════════════════════════════════════════════════════
#  Category 3: Historical Performance Report
# ═══════════════════════════════════════════════════════════


class MonthlyReturn(BaseModel):
    """Average return for a calendar month."""
    month: int  # 1-12
    month_name: str
    avg_return_pct: float = 0.0
    win_rate_pct: float = 0.0
    data_years: int = 0


class DayOfWeekReturn(BaseModel):
    """Average return by day of week."""
    day: int  # 0=Monday
    day_name: str
    avg_return_pct: float = 0.0
    positive_pct: float = 0.0


class HoldingHistorical(BaseModel):
    """Historical analysis for a single holding."""
    symbol: str
    # Backtest
    backtest_win_rate: float = 0.0
    backtest_avg_return: float = 0.0
    backtest_max_drawdown: float = 0.0
    backtest_total_trades: int = 0
    # Volatility
    current_volatility: float = 0.0  # 30-day annualized
    historical_avg_volatility: float = 0.0
    vol_regime: str = "normal"  # low | normal | high | extreme
    # Year performance
    ytd_return_pct: float = 0.0
    one_year_return_pct: float = 0.0
    # Current month seasonality
    current_month_avg_return: float = 0.0
    current_month_win_rate: float = 0.0


class HistoricalReport(BaseModel):
    """Historical performance analysis for the portfolio."""
    # Portfolio-level
    portfolio_ytd_return_pct: float = 0.0
    portfolio_1y_return_pct: float = 0.0
    avg_portfolio_volatility: float = 0.0
    vol_regime: str = "normal"

    # Seasonality for current month
    current_month: str = ""
    current_month_avg_return: float = 0.0
    current_month_win_rate: float = 0.0
    current_month_outlook: str = "neutral"  # favorable | neutral | unfavorable

    # Day of week pattern
    best_weekday: Optional[str] = None
    best_weekday_return: float = 0.0
    worst_weekday: Optional[str] = None
    worst_weekday_return: float = 0.0

    # Recent backtest
    portfolio_avg_win_rate: float = 0.0
    portfolio_avg_drawdown: float = 0.0

    # Per-holding
    holdings: List[HoldingHistorical] = []

    # Monthly returns (portfolio average)
    monthly_seasonality: List[MonthlyReturn] = []
    day_of_week_returns: List[DayOfWeekReturn] = []

    # AI narrative
    ai_summary: str = ""
    latency_ms: float = 0.0

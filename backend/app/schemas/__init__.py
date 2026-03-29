"""
Pattern Scan Schemas — Typed request/response models for Chart Pattern Intelligence.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PatternSignalFlags(BaseModel):
    """Binary flags indicating which technical patterns were detected."""
    macd_divergence: bool = Field(False, description="Bullish or bearish MACD divergence detected")
    ma_crossover: bool = Field(False, description="Golden or death cross detected (SMA50 vs SMA200)")
    macd_crossover_type: Optional[str] = Field(None, description="'bullish' or 'bearish' if divergence detected")
    ma_crossover_type: Optional[str] = Field(None, description="'golden_cross' or 'death_cross' if detected")


class BacktestMetrics(BaseModel):
    """Vectorized backtest results from vectorbt."""
    win_rate_pct: float = Field(0.0, description="Percentage of winning trades")
    avg_return_pct: float = Field(0.0, description="Average return per trade")
    max_drawdown_pct: float = Field(0.0, description="Maximum drawdown during backtest period")
    total_trades: int = Field(0, description="Number of trades executed in backtest")
    sharpe_ratio: Optional[float] = Field(None, description="Risk-adjusted return")
    profit_factor: Optional[float] = Field(None, description="Gross profit / gross loss")


class PatternScanResponse(BaseModel):
    """Success response for pattern scan endpoint."""
    ticker: str
    interval: str
    lookback: int
    data_points: int = Field(0, description="Number of OHLCV bars analyzed")
    signals: PatternSignalFlags
    backtest: BacktestMetrics
    summary: str = Field("", description="2-sentence plain English LLM summary")
    cached: bool = Field(False, description="True if result was served from cache")
    latency_ms: float = Field(0.0, description="Total processing time")


class PatternScanErrorResponse(BaseModel):
    """Error response for pattern scan endpoint."""
    error: str
    code: str  # e.g. "FEATURE_DISABLED", "DEPENDENCY_MISSING", "DATA_UNAVAILABLE"
    detail: Optional[str] = None

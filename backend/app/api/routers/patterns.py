"""
Pattern Scan Router — GET /api/v1/patterns/scan/{ticker}

Chart Pattern Intelligence endpoint with:
- Feature flag guard
- Dependency validation
- Input validation (ticker normalization, interval whitelist, lookback bounds)
- Threadpool execution for CPU-bound analysis
- LLM summary generation
- Graceful error responses
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.core.feature_flags import is_pattern_scan_enabled
from app.core.dependency_guards import check_pattern_deps
from app.core.observability import get_logger
from app.schemas.patterns import (
    PatternScanResponse,
    PatternScanErrorResponse,
    PatternSignalFlags,
    BacktestMetrics,
)

logger = get_logger("api.patterns")
router = APIRouter(prefix="/patterns")

VALID_INTERVALS = {"1minute", "30minute", "day"}


@router.get("/scan/{ticker}", response_model=PatternScanResponse)
async def scan_pattern(
    ticker: str,
    interval: str = Query("day", description="Candle interval: 1minute, 30minute, day"),
    lookback: int = Query(365, ge=30, le=730, description="Lookback days (30-730)"),
):
    """
    Full pattern scan: OHLCV → indicators → divergence/crossover detection → backtest → LLM summary.

    Returns detected technical patterns, vectorbt backtest metrics, and a plain English summary.
    """
    t0 = time.time()
    settings = get_settings()

    # ── Guard: Feature flag ──
    if not is_pattern_scan_enabled():
        return JSONResponse(
            status_code=503,
            content=PatternScanErrorResponse(
                error="Pattern scan feature is disabled",
                code="FEATURE_DISABLED",
                detail="Set ENABLE_PATTERN_SCAN=true in .env to enable",
            ).model_dump(),
        )

    # ── Guard: Dependencies ──
    deps_ok, deps_msg = check_pattern_deps()
    if not deps_ok:
        return JSONResponse(
            status_code=424,
            content=PatternScanErrorResponse(
                error="Missing dependency for pattern scan",
                code="DEPENDENCY_MISSING",
                detail=deps_msg,
            ).model_dump(),
        )

    # ── Validate inputs ──
    ticker = ticker.strip().upper()
    if not ticker or len(ticker) > 20:
        raise HTTPException(status_code=422, detail="Invalid ticker symbol")

    if interval not in VALID_INTERVALS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid interval '{interval}'. Must be one of: {', '.join(VALID_INTERVALS)}",
        )

    lookback = min(lookback, settings.pattern_scan_max_lookback)

    # ── Fetch OHLCV data ──
    from app.services.ohlcv_provider import fetch_ohlcv

    df = await fetch_ohlcv(ticker=ticker, interval=interval, lookback_days=lookback)

    if df.empty:
        return JSONResponse(
            status_code=424,
            content=PatternScanErrorResponse(
                error=f"No OHLCV data available for {ticker}",
                code="DATA_UNAVAILABLE",
                detail="Check if ticker is valid and market data provider is configured",
            ).model_dump(),
        )

    # ── Run heavy analysis in threadpool ──
    from app.services.pattern_scan_service import scan_sync

    result = await run_in_threadpool(scan_sync, df, ticker)

    signals: PatternSignalFlags = result["signals"]
    backtest: BacktestMetrics = result["backtest"]

    # ── LLM Summary ──
    from app.services.pattern_scan_service import summarize_with_llm

    try:
        summary = await summarize_with_llm(ticker, signals, backtest)
    except Exception as e:
        logger.warning("summary_generation_failed", ticker=ticker, error=str(e))
        summary = f"Pattern analysis completed for {ticker}. Results show {'active signals' if signals.macd_divergence or signals.ma_crossover else 'no strong patterns'}."

    total_ms = (time.time() - t0) * 1000

    logger.info(
        "pattern_scan_completed",
        ticker=ticker,
        interval=interval,
        lookback=lookback,
        macd_div=signals.macd_divergence,
        ma_cross=signals.ma_crossover,
        trades=backtest.total_trades,
        latency_ms=round(total_ms, 2),
    )

    return PatternScanResponse(
        ticker=ticker,
        interval=interval,
        lookback=lookback,
        data_points=result["data_points"],
        signals=signals,
        backtest=backtest,
        summary=summary,
        cached=False,
        latency_ms=round(total_ms, 2),
    )


@router.get("/scan/{ticker}/quick")
async def quick_scan(
    ticker: str,
    interval: str = Query("day", description="Candle interval"),
    lookback: int = Query(180, ge=30, le=365),
):
    """
    Quick scan — pattern detection only, skip backtest.
    Faster response for dashboard cards.
    """
    t0 = time.time()

    if not is_pattern_scan_enabled():
        return JSONResponse(status_code=503, content={"error": "Feature disabled", "code": "FEATURE_DISABLED"})

    ticker = ticker.strip().upper()

    from app.services.ohlcv_provider import fetch_ohlcv

    df = await fetch_ohlcv(ticker=ticker, interval=interval, lookback_days=lookback)

    if df.empty:
        return {"ticker": ticker, "error": "No data available", "signals": None}

    from app.services.pattern_scan_service import compute_indicators, detect_macd_divergence, detect_ma_crossover

    def _quick(df_in):
        df_out = compute_indicators(df_in)
        macd_d, macd_t = detect_macd_divergence(df_out)
        ma_c, ma_t = detect_ma_crossover(df_out)
        return {
            "macd_divergence": macd_d,
            "macd_crossover_type": macd_t,
            "ma_crossover": ma_c,
            "ma_crossover_type": ma_t,
        }

    result = await run_in_threadpool(_quick, df)
    elapsed = (time.time() - t0) * 1000

    return {
        "ticker": ticker,
        "interval": interval,
        "lookback": lookback,
        "data_points": len(df),
        "signals": result,
        "latency_ms": round(elapsed, 2),
    }


@router.post("/portfolio-scan")
async def portfolio_scan(request: dict):
    """
    Scan all portfolio holdings for candlestick patterns, technical signals,
    and generate BUY/SELL/HOLD recommendations.
    
    Expects: {"holdings": [{"symbol": "RELIANCE", "qty": 10, "buy_price": 1400.0}, ...]}
    """
    import asyncio
    t0 = time.time()

    if not is_pattern_scan_enabled():
        return JSONResponse(status_code=503, content={"error": "Feature disabled"})

    holdings = request.get("holdings", [])
    if not holdings:
        return {"holdings": [], "summary": {"total": 0, "buy": 0, "sell": 0, "hold": 0}}

    from app.services.candlestick_agent import scan_portfolio_holding

    # Run all holdings concurrently (capped at 5 parallel)
    semaphore = asyncio.Semaphore(5)

    async def scan_one(h):
        async with semaphore:
            try:
                return await scan_portfolio_holding(
                    symbol=h.get("symbol", "").upper(),
                    qty=int(h.get("qty", 0)),
                    buy_price=float(h.get("buy_price", 0)),
                    lookback_days=180,
                )
            except Exception as e:
                logger.error("holding_scan_error", symbol=h.get("symbol"), error=str(e))
                return {
                    "symbol": h.get("symbol", "???"),
                    "status": "error",
                    "error": str(e),
                }

    results = await asyncio.gather(*[scan_one(h) for h in holdings])

    # Summary
    actions = [r.get("recommendation", {}).get("action", "HOLD") for r in results if r.get("status") == "ok"]
    total_ms = (time.time() - t0) * 1000

    logger.info(
        "portfolio_scan_completed",
        holdings_count=len(holdings),
        buy_count=actions.count("BUY"),
        sell_count=actions.count("SELL"),
        hold_count=actions.count("HOLD"),
        latency_ms=round(total_ms, 2),
    )

    return {
        "holdings": results,
        "summary": {
            "total": len(results),
            "buy": actions.count("BUY"),
            "sell": actions.count("SELL"),
            "hold": actions.count("HOLD"),
            "scanned": len([r for r in results if r.get("status") == "ok"]),
        },
        "latency_ms": round(total_ms, 2),
    }


@router.get("/health")
async def pattern_health():
    """Health check for pattern scan subsystem."""
    deps_ok, deps_msg = check_pattern_deps()
    return {
        "enabled": is_pattern_scan_enabled(),
        "dependencies_ok": deps_ok,
        "dependencies_detail": deps_msg,
    }

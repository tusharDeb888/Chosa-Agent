"""
Intelligence Router — 3-category AI Portfolio Intelligence API.

POST /api/v1/intelligence/portfolio-health  → Portfolio condition & risk
POST /api/v1/intelligence/market-analysis   → Technical signals & patterns
POST /api/v1/intelligence/historical        → Seasonality & volatility
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.observability import get_logger
from app.schemas.intelligence import (
    IntelligenceRequest,
    PortfolioHealthReport,
    MarketAnalysisReport,
    HistoricalReport,
)

logger = get_logger("api.intelligence")
router = APIRouter(prefix="/intelligence")


@router.post("/portfolio-health", response_model=PortfolioHealthReport)
async def portfolio_health(req: IntelligenceRequest):
    """
    Category 1: Portfolio Health — P&L, diversification, risk assessment.
    Analyzes the current condition of all holdings.
    """
    if not req.holdings:
        raise HTTPException(status_code=422, detail="At least one holding is required")

    try:
        from app.services.intelligence_service import generate_portfolio_health
        report = await generate_portfolio_health(req.holdings)
        logger.info(
            "portfolio_health_generated",
            holdings=len(req.holdings),
            latency_ms=report.latency_ms,
        )
        return report
    except Exception as e:
        logger.error("portfolio_health_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Portfolio health analysis failed: {str(e)}")


@router.post("/market-analysis", response_model=MarketAnalysisReport)
async def market_analysis(req: IntelligenceRequest):
    """
    Category 2: Market Analysis — MACD, MA, candlestick patterns, sector momentum.
    Analyzes what's happening in the market for portfolio holdings.
    """
    if not req.holdings:
        raise HTTPException(status_code=422, detail="At least one holding is required")

    try:
        from app.services.intelligence_service import generate_market_analysis
        report = await generate_market_analysis(req.holdings)
        logger.info(
            "market_analysis_generated",
            holdings=len(req.holdings),
            latency_ms=report.latency_ms,
        )
        return report
    except Exception as e:
        logger.error("market_analysis_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Market analysis failed: {str(e)}")


@router.post("/historical", response_model=HistoricalReport)
async def historical_report(req: IntelligenceRequest):
    """
    Category 3: Historical Performance — seasonality, volatility, backtest.
    Analyzes how the market historically behaves for portfolio holdings.
    """
    if not req.holdings:
        raise HTTPException(status_code=422, detail="At least one holding is required")

    try:
        from app.services.intelligence_service import generate_historical_report
        report = await generate_historical_report(req.holdings)
        logger.info(
            "historical_report_generated",
            holdings=len(req.holdings),
            latency_ms=report.latency_ms,
        )
        return report
    except Exception as e:
        logger.error("historical_report_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Historical analysis failed: {str(e)}")


@router.get("/health")
async def intelligence_health():
    """Health check for the intelligence subsystem."""
    from app.core.dependency_guards import check_video_deps
    video_ok, video_msg = check_video_deps()
    return {
        "enabled": True,
        "categories": [
            "portfolio-health",
            "market-analysis",
            "historical",
        ],
        "video_available": video_ok,
        "video_detail": video_msg,
        "status": "ok",
    }


# ═══════════════════════════════════════════════════════════
#  Video Generation Endpoints
# ═══════════════════════════════════════════════════════════


@router.post("/generate-video")
async def generate_intelligence_video(
    req: dict,
    background_tasks: BackgroundTasks,
):
    """
    Generate a narrated video from an intelligence report.

    Body: { "category": "health|market|historical", "report_data": {...} }

    Returns job_id immediately — poll /intelligence/video-status/{job_id}.
    """
    from app.core.dependency_guards import check_video_deps

    # Guard: video deps
    deps_ok, deps_msg = check_video_deps()
    if not deps_ok:
        return JSONResponse(
            status_code=424,
            content={"error": "Missing video dependency", "detail": deps_msg},
        )

    category = req.get("category", "")
    report_data = req.get("report_data", {})

    if category not in ("health", "market", "historical"):
        raise HTTPException(status_code=422, detail="Invalid category. Must be health, market, or historical")

    if not report_data:
        raise HTTPException(status_code=422, detail="Report data is required")

    # Generate job ID
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    job_id = f"intel_{ts}_{uuid.uuid4().hex[:8]}"

    # Initialize job
    from app.services.portfolio_video_service import set_video_job, generate_portfolio_video

    set_video_job(job_id, {
        "status": "queued",
        "progress_pct": 0,
        "category": category,
    })

    # Launch background task
    background_tasks.add_task(
        generate_portfolio_video,
        job_id=job_id,
        category=category,
        report_data=report_data,
    )

    logger.info("intel_video_job_queued", job_id=job_id, category=category)

    return {
        "job_id": job_id,
        "status": "processing",
        "category": category,
    }


@router.get("/video-status/{job_id}")
async def intel_video_status(job_id: str):
    """Poll the status of an intelligence video generation job."""
    from app.services.portfolio_video_service import get_video_job

    job = get_video_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "job_id": job_id,
        "status": job.get("status", "unknown"),
        "progress_pct": job.get("progress_pct", 0),
        "video_url": job.get("video_url"),
        "filename": job.get("filename"),
        "category": job.get("category"),
        "error": job.get("error"),
        "elapsed_sec": job.get("elapsed_sec"),
    }

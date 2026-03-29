"""
Video Engine Router — POST /api/v1/video/generate + status polling.

AI Market Video Engine endpoint with:
- Feature flag guard
- Dependency validation
- Background task execution (non-blocking)
- Job status tracking
- File download endpoint
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from app.config import get_settings
from app.core.feature_flags import is_video_engine_enabled
from app.core.dependency_guards import check_video_deps
from app.core.observability import get_logger
from app.schemas.video import (
    VideoGenerateRequest,
    VideoGenerateResponse,
    VideoStatusResponse,
)

logger = get_logger("api.video")
router = APIRouter(prefix="/video")


@router.post("/generate", response_model=VideoGenerateResponse, status_code=202)
async def generate_video(
    req: VideoGenerateRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start video generation as a background job.
    Returns immediately with a job_id for status polling.
    """
    # ── Guard: Feature flag ──
    if not is_video_engine_enabled():
        return JSONResponse(
            status_code=503,
            content={
                "error": "Video engine feature is disabled",
                "code": "FEATURE_DISABLED",
                "detail": "Set ENABLE_VIDEO_ENGINE=true in .env to enable",
            },
        )

    # ── Guard: Dependencies ──
    deps_ok, deps_msg = check_video_deps()
    if not deps_ok:
        return JSONResponse(
            status_code=424,
            content={
                "error": "Missing dependency for video engine",
                "code": "DEPENDENCY_MISSING",
                "detail": deps_msg,
            },
        )

    # ── Validate & normalize ──
    ticker = req.ticker.strip().upper()
    if not ticker or len(ticker) > 20:
        raise HTTPException(status_code=422, detail="Invalid ticker symbol")

    # Generate job ID
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    job_id = f"vid_{ts}_{uuid.uuid4().hex[:8]}"

    # ── Initialize job ──
    from app.services.video_engine_service import set_job

    set_job(job_id, {
        "status": "queued",
        "progress_pct": 0,
        "ticker": ticker,
        "theme": req.theme.value,
        "duration_sec": req.duration_sec,
    })

    # ── Launch background task ──
    from app.services.video_engine_service import generate_video as run_pipeline

    background_tasks.add_task(
        run_pipeline,
        job_id=job_id,
        ticker=ticker,
        theme=req.theme.value,
        duration_sec=req.duration_sec,
        additional_tickers=req.additional_tickers,
    )

    logger.info(
        "video_job_queued",
        job_id=job_id,
        ticker=ticker,
        theme=req.theme.value,
        duration_sec=req.duration_sec,
    )

    return VideoGenerateResponse(
        job_id=job_id,
        status="processing",
        video_url=None,
        filename=None,
        duration_sec=req.duration_sec,
    )


@router.get("/status/{job_id}", response_model=VideoStatusResponse)
async def video_status(job_id: str):
    """
    Check the status of a video generation job.
    Poll this endpoint until status is 'completed' or 'failed'.
    """
    from app.services.video_engine_service import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return VideoStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        video_url=job.get("video_url"),
        filename=job.get("filename"),
        duration_sec=job.get("duration_sec", 45),
        progress_pct=job.get("progress_pct", 0),
        error=job.get("error"),
    )


@router.get("/stream/{filename}")
async def stream_video(filename: str):
    """
    Download/stream a generated video file.
    Validates filename to prevent path traversal.
    """
    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only .mp4 files supported")

    settings = get_settings()
    filepath = os.path.join(settings.video_output_dir, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        filepath,
        media_type="video/mp4",
        filename=filename,
    )


@router.get("/health")
async def video_health():
    """Health check for video engine subsystem."""
    deps_ok, deps_msg = check_video_deps()
    return {
        "enabled": is_video_engine_enabled(),
        "dependencies_ok": deps_ok,
        "dependencies_detail": deps_msg,
    }


@router.get("/jobs")
async def list_jobs():
    """List all video generation jobs (for debugging)."""
    from app.services.video_engine_service import _jobs

    return {
        "total": len(_jobs),
        "jobs": [
            {
                "job_id": jid,
                "status": data.get("status"),
                "progress_pct": data.get("progress_pct", 0),
                "video_url": data.get("video_url"),
            }
            for jid, data in _jobs.items()
        ],
    }

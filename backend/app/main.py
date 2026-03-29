"""
Alpha-Hunter — FastAPI Application Factory.

Initializes the API server, background workers, and lifecycle hooks.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.observability import setup_logging, setup_tracing, setup_metrics, get_logger
from app.db.engine import dispose_engine
from app.dependencies import close_redis, get_redis

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown hooks."""
    settings = get_settings()

    # ── Startup ──
    setup_logging(settings.log_level)
    setup_tracing()
    setup_metrics()
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        market_provider=settings.market_provider,
        agent_default_state=settings.agent_default_state,
    )

    # Initialize Redis connection
    redis_client = await get_redis()
    await redis_client.ping()
    logger.info("redis_connected")

    # Set initial agent state
    await redis_client.set("agent:state", settings.agent_default_state)

    # Start background workers
    worker_tasks = []
    try:
        from app.ingestion.worker import start_ingestion_worker
        from app.qualification.worker import start_qualification_worker
        from app.orchestrator.worker import start_orchestrator_worker
        from app.notifications.service import start_notification_worker
        from app.ingestion.filing_monitor import start_filing_monitor

        worker_tasks.append(asyncio.create_task(start_ingestion_worker()))
        worker_tasks.append(asyncio.create_task(start_qualification_worker()))
        worker_tasks.append(asyncio.create_task(start_orchestrator_worker()))
        worker_tasks.append(asyncio.create_task(start_notification_worker()))
        worker_tasks.append(asyncio.create_task(start_filing_monitor()))
        logger.info("background_workers_started", count=len(worker_tasks))
    except ImportError as e:
        logger.warning("worker_import_failed", error=str(e))

    yield

    # ── Shutdown ──
    logger.info("application_shutting_down")

    # Cancel background workers
    for task in worker_tasks:
        task.cancel()
    if worker_tasks:
        await asyncio.gather(*worker_tasks, return_exceptions=True)

    # Cleanup resources
    await close_redis()
    await dispose_engine()
    # Close Telegram bot
    try:
        from app.notifications.telegram import close_telegram_bot
        await close_telegram_bot()
    except Exception:
        pass
    logger.info("application_stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Autonomous Financial Agent Platform",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Register API Routes ──
    from app.api.v1 import agent, portfolio, alerts, ops, topology, chaos, orders, market
    from app.api.v1 import news, explain, actions, demo, telegram_bot
    from app.api.routers import patterns as pattern_router, video as video_router
    from app.api.routers import intelligence as intel_router
    from app.api.routers import chat as chat_router
    app.include_router(agent.router, prefix="/api/v1", tags=["Agent"])
    app.include_router(portfolio.router, prefix="/api/v1", tags=["Portfolio"])
    app.include_router(alerts.router, prefix="/api/v1", tags=["Alerts"])
    app.include_router(orders.router, prefix="/api/v1", tags=["Orders"])
    app.include_router(market.router, prefix="/api/v1", tags=["Market"])
    app.include_router(news.router, prefix="/api/v1", tags=["News"])
    app.include_router(explain.router, prefix="/api/v1", tags=["Explainability"])
    app.include_router(actions.router, prefix="/api/v1", tags=["Actions"])
    app.include_router(demo.router, prefix="/api/v1", tags=["Demo"])
    app.include_router(telegram_bot.router, prefix="/api/v1", tags=["Telegram"])
    app.include_router(ops.router, prefix="/api/v1", tags=["Operations"])
    app.include_router(topology.router, prefix="/api/v1", tags=["Topology"])
    app.include_router(chaos.router, prefix="/api/v1", tags=["Chaos"])
    # New modules
    app.include_router(pattern_router.router, prefix="/api/v1", tags=["Patterns"])
    app.include_router(video_router.router, prefix="/api/v1", tags=["Video"])
    app.include_router(intel_router.router, prefix="/api/v1", tags=["Intelligence"])
    app.include_router(chat_router.router, prefix="/api/v1", tags=["Chat"])

    # ── Static file mount for generated videos ──
    import os
    from fastapi.staticfiles import StaticFiles
    video_dir = settings.video_output_dir
    os.makedirs(video_dir, exist_ok=True)
    os.makedirs(settings.video_audio_dir, exist_ok=True)
    os.makedirs(settings.video_frames_dir, exist_ok=True)
    app.mount("/media/videos", StaticFiles(directory=video_dir), name="videos")


    # ── Root health check ──
    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "operational",
        }

    return app


# Application instance
app = create_app()

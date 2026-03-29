"""
Ingestion Worker — Always-on market data ingestor.

Continuously reads ticks from the market data provider, runs anomaly detection,
and emits SignalCandidate events to the stream bus.

PRD §17: Auto-restart with bounded retry and jitter. Health heartbeat every 5s.
"""

from __future__ import annotations

import asyncio
import json
import random
import time

from app.config import get_settings
from app.core.enums import AgentState, StreamTopic
from app.core.events import Event
from app.core.observability import get_logger, get_agent_metrics
from app.dependencies import get_redis
from app.ingestion.anomaly import AnomalyDetector
from app.ingestion.providers import MarketDataProvider
from app.ingestion.providers.mock import MockProvider
from app.streams.producer import StreamProducer
from app.control.kill_switch import KillSwitch

logger = get_logger("ingestion.worker")

# How often to refresh portfolio watch-list from Redis (seconds)
SYMBOL_REFRESH_INTERVAL = 300  # 5 minutes


def create_provider() -> MarketDataProvider:
    """Factory to create the configured market data provider."""
    settings = get_settings()
    if settings.market_provider == "upstox":
        from app.ingestion.providers.upstox import UpstoxProvider
        return UpstoxProvider(
            api_key=settings.upstox_api_key,
            api_secret=settings.upstox_api_secret,
            access_token=settings.upstox_access_token,
        )
    return MockProvider()


async def get_portfolio_symbols(redis_client) -> list[str]:
    """Read portfolio watch symbols from Redis. Falls back to default list."""
    try:
        raw = await redis_client.get("portfolio:watch_symbols")
        if raw:
            symbols = json.loads(raw)
            if symbols:
                logger.info("portfolio_symbols_loaded", count=len(symbols), symbols=symbols[:5])
                return symbols
    except Exception as e:
        logger.warning("portfolio_symbols_load_failed", error=str(e))
    # Default symbols
    return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "WIPRO", "ICICIBANK"]


async def start_ingestion_worker() -> None:
    """
    Main ingestion worker entry point.

    Implements:
    - Always-on loop with auto-restart
    - Bounded retry with exponential backoff + jitter
    - 5s heartbeat emission
    - Agent state gate (only processes when RUNNING)
    - Auto-DEGRADED transition after 3 consecutive crashes (PRD §17)
    """
    settings = get_settings()
    restart_count = 0
    max_restarts = settings.worker_max_restart_attempts
    backoff_base = settings.worker_restart_backoff_base_seconds
    backoff_max = settings.worker_restart_backoff_max_seconds

    while restart_count < max_restarts:
        try:
            await _run_ingestion_loop()
            # If loop exits cleanly, reset counter
            restart_count = 0
        except asyncio.CancelledError:
            logger.info("ingestion_worker_cancelled")
            return
        except Exception as e:
            restart_count += 1
            backoff = min(backoff_base * (2 ** restart_count), backoff_max)
            jitter = random.uniform(0, backoff * 0.3)
            wait_time = backoff + jitter

            logger.error(
                "ingestion_worker_crashed",
                error=str(e),
                restart_count=restart_count,
                max_restarts=max_restarts,
                retry_in_seconds=round(wait_time, 2),
            )

            # ── Auto-DEGRADED after 3 consecutive crashes ──
            if restart_count >= 3:
                try:
                    redis_client = await get_redis()
                    kill_switch = KillSwitch(redis_client)
                    current = await kill_switch.get_state()
                    if current == AgentState.RUNNING:
                        await kill_switch.transition(
                            AgentState.DEGRADED,
                            reason=f"ingestion_worker: {restart_count} consecutive crashes — auto-degraded",
                        )
                        logger.warning(
                            "auto_degraded_triggered",
                            restart_count=restart_count,
                            reason="consecutive_crash_threshold",
                        )
                except Exception as deg_err:
                    logger.error("auto_degrade_failed", error=str(deg_err))

            await asyncio.sleep(wait_time)

    logger.critical(
        "ingestion_worker_max_restarts_exceeded",
        max_restarts=max_restarts,
    )


async def _run_ingestion_loop() -> None:
    """Core ingestion loop — connect, stream, detect, emit."""
    settings = get_settings()
    redis_client = await get_redis()
    producer = StreamProducer(redis_client)
    provider = create_provider()
    detector = AnomalyDetector()

    # ── Load portfolio symbols from Redis and subscribe ──
    symbols = await get_portfolio_symbols(redis_client)
    await provider.subscribe(symbols)
    logger.info("ingestion_symbols_subscribed", symbols=symbols)

    # Import market hours check
    from app.ingestion.market_hours import is_market_open, get_market_status

    # Connect to market data source
    await provider.connect()
    market_status = get_market_status()
    logger.info(
        "ingestion_loop_started",
        provider=settings.market_provider,
        market_open=market_status["is_open"],
        market_status=market_status["status"],
        market_message=market_status["message"],
    )

    last_heartbeat = time.time()
    last_symbol_refresh = time.time()
    tick_count = 0

    try:
        async for tick in provider.stream_ticks():
            # ── Agent state gate ──
            agent_state = await redis_client.get("agent:state")
            if agent_state != AgentState.RUNNING:
                await asyncio.sleep(1)
                continue

            tick_count += 1

            # ── Refresh portfolio symbols every 5 minutes ──
            now = time.time()
            if now - last_symbol_refresh >= SYMBOL_REFRESH_INTERVAL:
                new_symbols = await get_portfolio_symbols(redis_client)
                await provider.subscribe(new_symbols)
                last_symbol_refresh = now
                logger.info("symbols_refreshed", count=len(new_symbols))

            # ── Emit heartbeat every 5s ──
            if now - last_heartbeat >= settings.worker_heartbeat_interval_seconds:
                await redis_client.set(
                    "worker:ingestion:heartbeat",
                    str(int(now)),
                    ex=30,
                )
                await redis_client.set(
                    "worker:ingestion:tick_count",
                    str(tick_count),
                )
                last_heartbeat = now

            # ── Anomaly detection ──
            signals = detector.process_tick(tick)

            # ── Emit signals to stream ──
            for signal in signals:
                event = Event(
                    idempotency_key=Event.generate_idempotency_key(
                        source=signal.source,
                        ticker=signal.symbol,
                        event_ts=signal.timestamp.isoformat(),
                        anomaly_type=signal.anomaly_type,
                    ),
                    topic=StreamTopic.SIGNALS_CANDIDATE,
                    event_type="signal.candidate",
                    payload=signal.model_dump(mode="json"),
                    ticker=signal.symbol,
                    signal_id=signal.signal_id,
                )
                await producer.publish(event)

    finally:
        await provider.close()
        logger.info("ingestion_loop_stopped", total_ticks=tick_count)

"""
Filing Monitor Worker — Background poller for corporate filings.

Polls corporate filing sources every 60 seconds. When a new filing is
detected for a portfolio-held symbol, emits a SignalCandidate to the
stream bus with anomaly_type=CORPORATE_FILING.

This ensures the agent reacts to news/filings BEFORE the price moves.
"""

from __future__ import annotations

import asyncio
import random
import time
import uuid

from datetime import datetime, timezone

from app.config import get_settings
from app.core.enums import AgentState, AnomalyType, StreamTopic
from app.core.events import Event
from app.core.schemas import SignalCandidate
from app.core.observability import get_logger
from app.dependencies import get_redis
from app.enrichment.filing_scraper import fetch_corporate_filings, MOCK_FILING_TEMPLATES, SECTOR_MAP
from app.streams.producer import StreamProducer

logger = get_logger("ingestion.filing_monitor")

# Symbols to monitor — top NSE stocks
MONITORED_SYMBOLS = list(SECTOR_MAP.keys())


async def start_filing_monitor() -> None:
    """
    Start the filing monitor worker.

    Polls for new corporate filings every 60 seconds.
    When a filing affects a monitored symbol, emits a SignalCandidate.
    """
    settings = get_settings()
    poll_interval = 60  # seconds
    seen_filing_ids: set[str] = set()

    logger.info("filing_monitor_started", monitored_symbols=len(MONITORED_SYMBOLS))

    while True:
        try:
            redis_client = await get_redis()

            # Check agent state
            agent_state = await redis_client.get("agent:state") or AgentState.PAUSED
            if agent_state != AgentState.RUNNING:
                await asyncio.sleep(5)
                continue

            # Emit heartbeat
            await redis_client.set(
                "worker:filing_monitor:heartbeat",
                str(int(time.time())),
                ex=120,
            )

            producer = StreamProducer(redis_client)

            # Pick a random subset of symbols to poll (avoid spamming all at once)
            symbols_to_check = random.sample(
                MONITORED_SYMBOLS, min(5, len(MONITORED_SYMBOLS))
            )

            for symbol in symbols_to_check:
                try:
                    filings = await fetch_corporate_filings(symbol, max_results=2)

                    for filing in filings:
                        if filing.filing_id in seen_filing_ids:
                            continue

                        seen_filing_ids.add(filing.filing_id)

                        # Only keep last 500 seen IDs to prevent memory leak
                        if len(seen_filing_ids) > 500:
                            seen_filing_ids.clear()

                        # Emit signal for each affected ticker
                        for ticker in filing.affected_tickers:
                            confidence = _filing_confidence(filing.severity)

                            signal = SignalCandidate(
                                signal_id=f"filing-{uuid.uuid4().hex[:12]}",
                                symbol=ticker,
                                anomaly_type=AnomalyType.CORPORATE_FILING,
                                price=0.0,  # Filing doesn't have a price — enrichment will fetch
                                volume=0,
                                z_score=0.0,
                                vwap_deviation_pct=0.0,
                                confidence=confidence,
                                timestamp=filing.published_at,
                                source=filing.source_name or "filing_monitor",
                                metadata={
                                    "filing_id": filing.filing_id,
                                    "filing_type": filing.filing_type,
                                    "title": filing.title,
                                    "summary": filing.summary[:300],
                                    "plain_english_summary": filing.plain_english_summary,
                                    "source_url": filing.source_url,
                                    "severity": filing.severity,
                                    "source_name": filing.source_name,
                                },
                            )

                            event = Event(
                                idempotency_key=Event.generate_idempotency_key(
                                    source=filing.source_name,
                                    ticker=ticker,
                                    event_ts=filing.published_at.isoformat(),
                                    anomaly_type=AnomalyType.CORPORATE_FILING,
                                ),
                                topic=StreamTopic.SIGNALS_CANDIDATE,
                                event_type="signal.candidate.filing",
                                payload=signal.model_dump(mode="json"),
                                ticker=ticker,
                                signal_id=signal.signal_id,
                            )
                            await producer.publish(event)

                            logger.info(
                                "filing_signal_emitted",
                                ticker=ticker,
                                filing_type=filing.filing_type,
                                title=filing.title[:60],
                                severity=filing.severity,
                            )

                except Exception as e:
                    logger.debug(
                        "filing_check_failed",
                        symbol=symbol,
                        error=str(e),
                    )

            await asyncio.sleep(poll_interval)

        except asyncio.CancelledError:
            logger.info("filing_monitor_cancelled")
            return
        except Exception as e:
            logger.error("filing_monitor_error", error=str(e))
            await asyncio.sleep(10)


def _filing_confidence(severity: str) -> float:
    """Map filing severity to initial confidence score."""
    return {
        "critical": 85.0,
        "high": 70.0,
        "medium": 50.0,
        "low": 30.0,
    }.get(severity, 40.0)

"""
Stream Producer — XADD wrapper with per-topic retention policy.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis

from app.config import get_settings
from app.core.events import Event
from app.core.enums import StreamTopic
from app.core.observability import get_logger

logger = get_logger("streams.producer")


class StreamProducer:
    """
    Publishes events to Redis Streams with automatic retention trimming.

    Uses XADD with MAXLEN ~ (approximate trimming) for high-volume topics
    and exact retention for critical replay topics.
    """

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client
        self._settings = get_settings()
        self._maxlen_map = self._build_maxlen_map()

    def _build_maxlen_map(self) -> dict[str, int]:
        """Map each topic to its max stream length."""
        s = self._settings
        return {
            StreamTopic.MARKET_TICKS_RAW: s.stream_retention_ticks_maxlen,
            StreamTopic.SIGNALS_CANDIDATE: s.stream_retention_signals_maxlen,
            StreamTopic.SIGNALS_QUALIFIED: s.stream_retention_signals_maxlen,
            StreamTopic.AGENT_TASKS: s.stream_retention_signals_maxlen,
            StreamTopic.AGENT_DECISIONS: s.stream_retention_decisions_maxlen,
            StreamTopic.ALERTS_USER_FEED: s.stream_retention_decisions_maxlen,
        }

    async def publish(self, event: Event) -> str:
        """
        Publish an event to its topic stream.

        Returns the stream entry ID assigned by Redis.
        """
        topic = event.topic
        maxlen = self._maxlen_map.get(topic, 10000)

        # Use approximate trimming for high-volume, exact for critical
        approximate = topic in (
            StreamTopic.MARKET_TICKS_RAW,
            StreamTopic.SIGNALS_CANDIDATE,
        )

        stream_data = event.to_stream_dict()

        entry_id = await self._redis.xadd(
            topic,
            stream_data,
            maxlen=maxlen,
            approximate=approximate,
        )

        logger.debug(
            "event_published",
            topic=topic,
            event_id=event.event_id,
            entry_id=entry_id,
            ticker=event.ticker,
        )

        return entry_id

    async def publish_batch(self, events: list[Event]) -> list[str]:
        """Publish a batch of events. Returns list of entry IDs."""
        entry_ids = []
        pipe = self._redis.pipeline()
        for event in events:
            topic = event.topic
            maxlen = self._maxlen_map.get(topic, 10000)
            approximate = topic in (
                StreamTopic.MARKET_TICKS_RAW,
                StreamTopic.SIGNALS_CANDIDATE,
            )
            pipe.xadd(topic, event.to_stream_dict(), maxlen=maxlen, approximate=approximate)

        results = await pipe.execute()
        for result in results:
            entry_ids.append(result)

        logger.debug("batch_published", count=len(events))
        return entry_ids

    async def get_stream_length(self, topic: str) -> int:
        """Get the current length of a stream."""
        return await self._redis.xlen(topic)

    async def get_stream_info(self, topic: str) -> dict[str, Any]:
        """Get stream metadata."""
        try:
            info = await self._redis.xinfo_stream(topic)
            return info
        except redis.ResponseError:
            return {}

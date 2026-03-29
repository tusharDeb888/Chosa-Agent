"""
Dead Letter Queue — Routes failed events after max retry attempts.
"""

from __future__ import annotations

import time

import redis.asyncio as redis

from app.core.events import Event
from app.core.enums import StreamTopic
from app.core.observability import get_logger

logger = get_logger("streams.dlq")


class DeadLetterQueue:
    """
    Routes poison messages to DLQ streams after max retry attempts.

    DLQ streams have no aggressive trimming (preserved for audit/replay).
    """

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client

    async def route_to_dlq(
        self,
        event: Event,
        error: Exception,
        source_topic: str,
    ) -> str:
        """
        Move a failed event to its DLQ topic.

        Attaches failure metadata for later inspection.
        """
        dlq_topic = StreamTopic.dlq_for(source_topic)

        # Build DLQ envelope with failure context
        dlq_event = Event(
            event_id=f"dlq:{event.event_id}",
            idempotency_key=event.idempotency_key,
            topic=dlq_topic,
            event_type=f"dlq.{event.event_type}",
            payload={
                "original_event": event.model_dump(),
                "failure": {
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "source_topic": source_topic,
                    "attempt": event.attempt,
                    "max_attempts": event.max_attempts,
                    "routed_at": time.time(),
                },
            },
            ticker=event.ticker,
            signal_id=event.signal_id,
            user_id=event.user_id,
            tenant_id=event.tenant_id,
            trace_id=event.trace_id,
            workflow_id=event.workflow_id,
        )

        # DLQ streams: no trimming
        entry_id = await self._redis.xadd(
            dlq_topic,
            dlq_event.to_stream_dict(),
        )

        logger.warning(
            "event_routed_to_dlq",
            source_topic=source_topic,
            dlq_topic=dlq_topic,
            event_id=event.event_id,
            error_type=type(error).__name__,
            attempt=event.attempt,
        )

        return entry_id

    async def should_dlq(self, event: Event) -> bool:
        """Check if an event has exceeded max retry attempts."""
        return event.attempt >= event.max_attempts

    async def get_dlq_depth(self, source_topic: str) -> int:
        """Get the number of events in a DLQ."""
        dlq_topic = StreamTopic.dlq_for(source_topic)
        try:
            return await self._redis.xlen(dlq_topic)
        except Exception:
            return 0

    async def get_all_dlq_depths(self) -> dict[str, int]:
        """Get DLQ depths for all known topics."""
        topics = [
            StreamTopic.SIGNALS_CANDIDATE,
            StreamTopic.SIGNALS_QUALIFIED,
            StreamTopic.AGENT_TASKS,
            StreamTopic.AGENT_DECISIONS,
            StreamTopic.ALERTS_USER_FEED,
        ]
        depths = {}
        for topic in topics:
            depths[topic] = await self.get_dlq_depth(topic)
        return depths

    async def replay_dlq(
        self,
        source_topic: str,
        count: int = 10,
    ) -> list[Event]:
        """
        Read events from a DLQ for replay or inspection.

        Does NOT acknowledge — events remain until manually handled.
        """
        dlq_topic = StreamTopic.dlq_for(source_topic)
        results = await self._redis.xrange(dlq_topic, count=count)

        events = []
        for msg_id, msg_data in results:
            try:
                event = Event.from_stream_dict(msg_data)
                events.append(event)
            except Exception as e:
                logger.error("dlq_read_failed", error=str(e))

        return events

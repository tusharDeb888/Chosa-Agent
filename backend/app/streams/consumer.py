"""
Stream Consumer — XREADGROUP, XACK, XAUTOCLAIM with bounded retries.
"""

from __future__ import annotations

import asyncio
import socket
import time
from typing import Any, Callable, Coroutine

import redis.asyncio as redis

from app.config import get_settings
from app.core.events import Event, EventBatch
from app.core.enums import StreamTopic
from app.core.observability import get_logger

logger = get_logger("streams.consumer")


class StreamConsumer:
    """
    Redis Streams consumer with consumer groups.

    Features:
    - Automatic consumer group creation
    - XREADGROUP with configurable block timeout and batch size
    - XACK on successful processing
    - XAUTOCLAIM for pending message recovery
    - Bounded retry with DLQ routing
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        topic: str,
        group: str | None = None,
        consumer_name: str | None = None,
    ):
        self._redis = redis_client
        self._topic = topic
        self._settings = get_settings()
        self._group = group or self._settings.stream_consumer_group
        self._consumer = consumer_name or f"worker-{socket.gethostname()}-{id(self)}"
        self._running = False

    async def ensure_group(self) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            await self._redis.xgroup_create(
                self._topic,
                self._group,
                id="0",
                mkstream=True,
            )
            logger.info(
                "consumer_group_created",
                topic=self._topic,
                group=self._group,
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def read_batch(
        self,
        count: int | None = None,
        block_ms: int | None = None,
    ) -> EventBatch:
        """
        Read a batch of messages from the stream using XREADGROUP.

        Returns an EventBatch with deserialized events.
        """
        count = count or self._settings.stream_batch_size
        block_ms = block_ms or self._settings.stream_block_ms

        results = await self._redis.xreadgroup(
            groupname=self._group,
            consumername=self._consumer,
            streams={self._topic: ">"},
            count=count,
            block=block_ms,
        )

        events = []
        if results:
            for stream_name, messages in results:
                for msg_id, msg_data in messages:
                    try:
                        event = Event.from_stream_dict(msg_data)
                        event.event_id = msg_id if isinstance(msg_id, str) else msg_id.decode()
                        events.append(event)
                    except Exception as e:
                        logger.error(
                            "event_deserialize_failed",
                            msg_id=msg_id,
                            error=str(e),
                        )

        return EventBatch(
            events=events,
            stream_id=self._topic,
            consumer_group=self._group,
            consumer_name=self._consumer,
        )

    async def ack(self, event_id: str) -> None:
        """Acknowledge a successfully processed message."""
        await self._redis.xack(self._topic, self._group, event_id)

    async def ack_batch(self, event_ids: list[str]) -> None:
        """Acknowledge multiple messages."""
        if event_ids:
            await self._redis.xack(self._topic, self._group, *event_ids)

    async def claim_pending(
        self,
        min_idle_ms: int = 30000,
        count: int = 10,
    ) -> list[Event]:
        """
        Claim pending messages from crashed consumers using XAUTOCLAIM.

        Messages idle for longer than min_idle_ms are reclaimed.
        """
        try:
            result = await self._redis.xautoclaim(
                self._topic,
                self._group,
                self._consumer,
                min_idle_time=min_idle_ms,
                start_id="0-0",
                count=count,
            )
            # result is (next_start_id, messages, deleted_ids)
            if result and len(result) >= 2:
                messages = result[1]
                events = []
                for msg_id, msg_data in messages:
                    try:
                        event = Event.from_stream_dict(msg_data)
                        event.event_id = msg_id if isinstance(msg_id, str) else msg_id.decode()
                        events.append(event)
                    except Exception as e:
                        logger.error("claim_deserialize_failed", error=str(e))
                return events
        except Exception as e:
            logger.error("xautoclaim_failed", error=str(e))

        return []

    async def get_pending_count(self) -> int:
        """Get count of pending messages for this consumer group."""
        try:
            info = await self._redis.xpending(self._topic, self._group)
            return info.get("pending", 0) if isinstance(info, dict) else 0
        except Exception:
            return 0

    async def run(
        self,
        handler: Callable[[Event], Coroutine[Any, Any, None]],
        on_error: Callable[[Event, Exception], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """
        Main consumer loop — continuously read and process events.

        Respects self._running flag for graceful shutdown.
        """
        await self.ensure_group()
        self._running = True

        logger.info(
            "consumer_started",
            topic=self._topic,
            group=self._group,
            consumer=self._consumer,
        )

        while self._running:
            try:
                # First, try to claim any pending messages from crashed workers
                pending = await self.claim_pending()
                for event in pending:
                    await self._process_event(event, handler, on_error)

                # Then read new messages
                batch = await self.read_batch()
                for event in batch.events:
                    await self._process_event(event, handler, on_error)

            except asyncio.CancelledError:
                logger.info("consumer_cancelled", topic=self._topic)
                break
            except Exception as e:
                logger.error("consumer_loop_error", error=str(e), topic=self._topic)
                await asyncio.sleep(1)

        logger.info("consumer_stopped", topic=self._topic)

    async def _process_event(
        self,
        event: Event,
        handler: Callable[[Event], Coroutine[Any, Any, None]],
        on_error: Callable[[Event, Exception], Coroutine[Any, Any, None]] | None,
    ) -> None:
        """Process a single event with error handling."""
        try:
            await handler(event)
            await self.ack(event.event_id)
        except Exception as e:
            logger.error(
                "event_processing_failed",
                event_id=event.event_id,
                attempt=event.attempt,
                error=str(e),
            )
            if on_error:
                await on_error(event, e)

    def stop(self) -> None:
        """Signal the consumer to stop."""
        self._running = False

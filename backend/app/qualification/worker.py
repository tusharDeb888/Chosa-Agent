"""
Qualification Worker — Consumes signal.candidate events, qualifies, and emits.
"""

from __future__ import annotations

import asyncio

from app.config import get_settings
from app.core.enums import AgentState, StreamTopic
from app.core.events import Event
from app.core.schemas import SignalCandidate
from app.core.observability import get_logger
from app.dependencies import get_redis
from app.qualification.service import SignalQualifier
from app.streams.consumer import StreamConsumer
from app.streams.producer import StreamProducer
from app.streams.dlq import DeadLetterQueue

logger = get_logger("qualification.worker")


async def start_qualification_worker() -> None:
    """Start the signal qualification consumer worker."""
    settings = get_settings()
    redis_client = await get_redis()
    consumer = StreamConsumer(redis_client, StreamTopic.SIGNALS_CANDIDATE)
    producer = StreamProducer(redis_client)
    dlq = DeadLetterQueue(redis_client)
    qualifier = SignalQualifier()

    async def handle_event(event: Event) -> None:
        """Process a single signal candidate event."""
        # Check agent state
        agent_state = await redis_client.get("agent:state") or AgentState.PAUSED

        # Deserialize signal
        signal = SignalCandidate(**event.payload)

        # Qualify
        result = qualifier.qualify(signal, agent_state)

        if hasattr(result, "qualified_at"):
            # QualifiedSignal — emit to next stage
            qualified_event = Event(
                idempotency_key=event.idempotency_key,
                topic=StreamTopic.SIGNALS_QUALIFIED,
                event_type="signal.qualified",
                payload=result.model_dump(mode="json"),
                ticker=event.ticker,
                signal_id=result.signal_id,
                trace_id=event.trace_id,
            )
            await producer.publish(qualified_event)
        else:
            # RejectedSignal — log and skip
            logger.debug(
                "signal_rejected_by_qualification",
                signal_id=result.signal_id,
                reason=result.reason_code,
            )

    async def handle_error(event: Event, error: Exception) -> None:
        """Route failed events to DLQ if max retries exceeded."""
        event.attempt += 1
        if await dlq.should_dlq(event):
            await dlq.route_to_dlq(event, error, StreamTopic.SIGNALS_CANDIDATE)
        else:
            logger.warning(
                "qualification_retry",
                event_id=event.event_id,
                attempt=event.attempt,
            )

    await consumer.run(handler=handle_event, on_error=handle_error)

"""
Notification Service — WebSocket + SSE delivery with at-least-once semantics.

Consumes from alerts.user_feed stream and fans out to connected clients.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis

from app.config import get_settings
from app.core.enums import StreamTopic
from app.core.events import Event
from app.core.observability import get_logger
from app.dependencies import get_redis
from app.streams.consumer import StreamConsumer

logger = get_logger("notifications.service")

# In-memory connected clients (WebSocket + SSE)
_ws_clients: dict[str, set] = {}  # user_id -> set of websocket connections
_sse_queues: dict[str, asyncio.Queue] = {}  # user_id -> SSE queue


def register_ws_client(user_id: str, ws: Any) -> None:
    """Register a WebSocket connection for a user."""
    if user_id not in _ws_clients:
        _ws_clients[user_id] = set()
    _ws_clients[user_id].add(ws)
    logger.info("ws_client_registered", user_id=user_id)


def unregister_ws_client(user_id: str, ws: Any) -> None:
    """Remove a WebSocket connection."""
    if user_id in _ws_clients:
        _ws_clients[user_id].discard(ws)
        if not _ws_clients[user_id]:
            del _ws_clients[user_id]
    logger.info("ws_client_unregistered", user_id=user_id)


def get_sse_queue(user_id: str) -> asyncio.Queue:
    """Get or create an SSE queue for a user."""
    if user_id not in _sse_queues:
        _sse_queues[user_id] = asyncio.Queue(maxsize=100)
    return _sse_queues[user_id]


def remove_sse_queue(user_id: str) -> None:
    """Remove SSE queue on disconnect."""
    _sse_queues.pop(user_id, None)


async def broadcast_to_user(user_id: str, data: dict) -> None:
    """Send data to all connected clients (WS + SSE) for a user."""
    payload = json.dumps(data, default=str)

    # ── WebSocket broadcast ──
    if user_id in _ws_clients:
        dead_connections = set()
        for ws in _ws_clients[user_id]:
            try:
                await ws.send_text(payload)
            except Exception:
                dead_connections.add(ws)
        # Cleanup dead connections
        for ws in dead_connections:
            _ws_clients[user_id].discard(ws)

    # ── SSE queue push ──
    if user_id in _sse_queues:
        try:
            _sse_queues[user_id].put_nowait(data)
        except asyncio.QueueFull:
            logger.warning("sse_queue_full", user_id=user_id)

    # ── Broadcast to "all" channel for dashboard ──
    if "all" in _ws_clients:
        for ws in _ws_clients["all"]:
            try:
                await ws.send_text(payload)
            except Exception:
                pass

    if "all" in _sse_queues:
        try:
            _sse_queues["all"].put_nowait(data)
        except asyncio.QueueFull:
            pass


async def start_notification_worker() -> None:
    """Consume alert events and fan out to connected clients + Telegram."""
    redis_client = await get_redis()
    consumer = StreamConsumer(
        redis_client,
        StreamTopic.ALERTS_USER_FEED,
        consumer_name="notification-worker",
    )

    async def handle_event(event: Event) -> None:
        """Deliver alert to connected user clients + Telegram."""
        user_id = event.user_id
        payload = event.payload

        await broadcast_to_user(user_id, payload)
        # Also broadcast to "all" for dashboard feed
        await broadcast_to_user("all", payload)

        # ── Telegram delivery (fire-and-forget) ──
        try:
            from app.notifications.telegram import send_telegram_alert
            asyncio.create_task(send_telegram_alert(payload))
        except Exception:
            pass  # Telegram is optional, never block the pipeline

        logger.debug(
            "alert_delivered",
            user_id=user_id,
            signal_id=event.signal_id,
        )

    await consumer.run(handler=handle_event)

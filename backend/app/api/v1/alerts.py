"""
Alerts API Routes — WebSocket and SSE endpoints for real-time delivery.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import StreamingResponse

from app.notifications.service import (
    register_ws_client,
    unregister_ws_client,
    get_sse_queue,
    remove_sse_queue,
)
from app.core.observability import get_logger

logger = get_logger("api.alerts")
router = APIRouter(prefix="/alerts")


@router.websocket("/ws")
async def alerts_websocket(
    websocket: WebSocket,
    user_id: str = Query(default="all"),
):
    """
    WebSocket endpoint for real-time alert delivery.

    Connect with ?user_id=<id> to receive user-specific alerts,
    or use ?user_id=all for all alerts (dashboard mode).
    """
    await websocket.accept()
    register_ws_client(user_id, websocket)

    logger.info("ws_connected", user_id=user_id)

    try:
        while True:
            # Keep connection alive — listen for client messages
            data = await websocket.receive_text()
            # Client can send ping/pong or control messages
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("ws_disconnected", user_id=user_id)
    except Exception as e:
        logger.error("ws_error", user_id=user_id, error=str(e))
    finally:
        unregister_ws_client(user_id, websocket)


@router.get("/stream")
async def alerts_sse(user_id: str = Query(default="all")):
    """
    SSE endpoint for real-time alert delivery (fallback for environments
    that don't support WebSocket).

    Connect with ?user_id=<id> for user-specific alerts.
    """

    async def event_generator():
        queue = get_sse_queue(user_id)
        logger.info("sse_connected", user_id=user_id)

        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data, default=str)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            remove_sse_queue(user_id)
            logger.info("sse_disconnected", user_id=user_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

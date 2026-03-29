"""
Agent API Routes — Lifecycle and status management.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException

from app.core.enums import AgentState
from app.core.schemas import LifecycleRequest, AgentStatusResponse
from app.core.exceptions import AgentStateError
from app.control.kill_switch import KillSwitch
from app.dependencies import get_redis

router = APIRouter(prefix="/agent")


@router.post("/lifecycle", response_model=dict)
async def change_agent_state(
    request: LifecycleRequest,
    redis_client=Depends(get_redis),
):
    """
    Change agent lifecycle state.

    Valid states: RUNNING, PAUSED, TERMINATED, DEGRADED
    """
    try:
        target = AgentState(request.target_state)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state: {request.target_state}. Must be one of: {[s.value for s in AgentState]}",
        )

    kill_switch = KillSwitch(redis_client)
    try:
        new_state = await kill_switch.transition(
            target_state=target,
            reason=request.reason,
            force=request.force,
        )

        # ── Fire Telegram startup notification when going RUNNING ──
        if new_state == AgentState.RUNNING:
            asyncio.create_task(_fire_startup_notification(redis_client))

        return {
            "status": "ok",
            "state": new_state.value,
            "message": f"Agent transitioned to {new_state.value}",
        }
    except AgentStateError as e:
        raise HTTPException(status_code=400, detail=e.message)


async def _fire_startup_notification(redis_client) -> None:
    """Fire-and-forget: send Telegram startup alert with symbol list and market status."""
    try:
        from app.notifications.telegram import send_startup_notification
        from app.ingestion.market_hours import get_market_status

        # Get watched symbols from Redis
        raw = await redis_client.get("portfolio:watch_symbols")
        symbols: list[str] = json.loads(raw) if raw else ["RELIANCE", "TCS", "HDFCBANK", "INFY"]

        market_info = get_market_status()
        market_str = f"{market_info['status']} ({market_info['current_time_ist']} IST)"

        await send_startup_notification(symbols=symbols, market_status=market_str)
    except Exception:
        pass  # Telegram is optional — never block the pipeline


@router.get("/status", response_model=dict)
async def get_agent_status(redis_client=Depends(get_redis)):
    """Get current agent runtime status."""
    kill_switch = KillSwitch(redis_client)
    state_info = await kill_switch.get_state_info()

    # Get worker heartbeats
    ingestion_hb = await redis_client.get("worker:ingestion:heartbeat")
    tick_count = await redis_client.get("worker:ingestion:tick_count")

    return {
        **state_info,
        "workers": {
            "ingestion": {
                "last_heartbeat": ingestion_hb,
                "tick_count": tick_count,
            },
        },
    }

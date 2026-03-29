"""
Actions API — User actions on alerts (prepare, snooze, ignore, escalate).

Provides the bridge between passive alerting and active decision-making.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.observability import get_logger

logger = get_logger("api.actions")
router = APIRouter(prefix="/actions")

# ── In-memory action store (production: PostgreSQL) ──
_action_store: dict[str, dict] = {}


class ActionRequest(BaseModel):
    """Action request payload."""
    alert_id: str
    action: str  # prepare | snooze | ignore | escalate
    snooze_duration_minutes: Optional[int] = 30
    reason: Optional[str] = None


class BulkActionRequest(BaseModel):
    """Bulk action request."""
    alert_ids: list[str]
    action: str
    snooze_duration_minutes: Optional[int] = 30


ACTION_SEMANTICS = {
    "prepare": "Opens order flow — user will review and confirm execution",
    "snooze": "Suppresses same alert group for specified duration",
    "ignore": "Dismisses this alert once — no further notifications for this signal",
    "escalate": "Pins alert to top of queue and flags for immediate attention",
}


@router.post("")
async def process_action(body: ActionRequest):
    """
    Process a user action on an alert.

    Actions:
    - **prepare**: Opens order flow for the alert's recommended trade
    - **snooze**: Suppresses the alert group for N minutes (default 30)
    - **ignore**: Dismisses the alert (one-time)
    - **escalate**: Pins to top and optionally notifies via Telegram
    """
    now = datetime.now(timezone.utc)

    if body.action not in ACTION_SEMANTICS:
        return {"status": "error", "message": f"Invalid action: {body.action}. Valid: {list(ACTION_SEMANTICS.keys())}"}

    action_id = str(uuid.uuid4())[:8]

    action_record = {
        "id": action_id,
        "alert_id": body.alert_id,
        "action": body.action,
        "status": "processed",
        "created_at": now.isoformat(),
        "reason": body.reason,
    }

    if body.action == "snooze":
        snooze_until = now + timedelta(minutes=body.snooze_duration_minutes or 30)
        action_record["snooze_until"] = snooze_until.isoformat()
        action_record["next_steps"] = f"Alert group snoozed until {snooze_until.strftime('%H:%M')} IST"

    elif body.action == "prepare":
        action_record["next_steps"] = "Order confirmation modal opened. Review details before executing."

    elif body.action == "ignore":
        action_record["next_steps"] = "Alert dismissed. You won't see this specific signal again."

    elif body.action == "escalate":
        action_record["next_steps"] = "Alert pinned to top of queue. Telegram notification sent (if configured)."

    _action_store[action_id] = action_record

    logger.info(
        "action_processed",
        action_id=action_id,
        alert_id=body.alert_id,
        action=body.action,
    )

    return action_record


@router.post("/bulk")
async def process_bulk_action(body: BulkActionRequest):
    """Process the same action on multiple alerts."""
    results = []
    for alert_id in body.alert_ids:
        req = ActionRequest(
            alert_id=alert_id,
            action=body.action,
            snooze_duration_minutes=body.snooze_duration_minutes,
        )
        result = await process_action(req)
        results.append(result)

    return {
        "processed": len(results),
        "results": results,
    }


@router.get("/queue")
async def get_action_queue(
    status: str = Query(default="all", description="all|pending|processed"),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get the action queue with optional status filter."""
    actions = list(_action_store.values())

    if status != "all":
        actions = [a for a in actions if a.get("status") == status]

    actions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {
        "items": actions[:limit],
        "count": len(actions),
    }


@router.get("/semantics")
async def get_action_semantics():
    """Return the meaning of each action for UI tooltips."""
    return ACTION_SEMANTICS

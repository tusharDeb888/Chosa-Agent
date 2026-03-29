"""
Orders API Routes — 1-click order confirmation endpoints.

Phase 1: Advisory mode only — logs confirmation but doesn't place real trades.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.observability import get_logger
from app.execution.service import OrderStagingService

logger = get_logger("api.orders")
router = APIRouter(prefix="/orders")

_service: OrderStagingService | None = None


def _get_service() -> OrderStagingService:
    global _service
    if _service is None:
        _service = OrderStagingService()
    return _service


@router.post("/confirm/{order_ticket_id}")
async def confirm_order(order_ticket_id: str):
    """
    Confirm a staged order.

    Phase 1: Advisory mode — logs the confirmation but doesn't place a trade.
    """
    service = _get_service()
    order = await service.confirm_order(order_ticket_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order ticket not found")

    return {
        "status": "ok",
        "order": order.model_dump(mode="json"),
        "message": (
            f"Order confirmed: {order.action} {order.quantity} shares of {order.symbol} "
            f"at ₹{order.price:,.2f} (Total: ₹{order.estimated_value:,.2f}). "
            "Advisory mode — order logged for execution tracking."
        ),
    }


@router.post("/dismiss/{order_ticket_id}")
async def dismiss_order(order_ticket_id: str):
    """Dismiss/cancel a staged order."""
    service = _get_service()
    order = await service.dismiss_order(order_ticket_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order ticket not found")

    return {
        "status": "ok",
        "order": order.model_dump(mode="json"),
        "message": "Order dismissed.",
    }


@router.get("/staged")
async def list_staged_orders():
    """List all pending staged orders."""
    service = _get_service()
    orders = service.get_staged_orders()
    return {
        "count": len(orders),
        "orders": [o.model_dump(mode="json") for o in orders],
    }


@router.get("/{order_ticket_id}")
async def get_order(order_ticket_id: str):
    """Get details of a specific order."""
    service = _get_service()
    order = service.get_order(order_ticket_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order ticket not found")

    return order.model_dump(mode="json")

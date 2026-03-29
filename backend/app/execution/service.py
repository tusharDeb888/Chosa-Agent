"""
Order Staging Service — Pre-computes order tickets for 1-click execution.

Advisory mode only in Phase 1 — no actual order placement.
Computes exact quantity, price, and ₹ value from portfolio context.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta

from app.core.enums import Decision, OrderStatus
from app.core.schemas import (
    GuardedDecision,
    PortfolioCanonical,
    PortfolioContext,
    StagedOrder,
)
from app.core.observability import get_logger, traced

logger = get_logger("execution.service")

# In-memory store for staged orders (Phase 1 — would be DB in production)
_staged_orders: dict[str, StagedOrder] = {}


class OrderStagingService:
    """
    Computes and stages order tickets for 1-click execution.

    For BUY/SELL decisions:
    - Calculates exact quantity based on portfolio impact
    - Sets limit price from current signal price ± buffer
    - Computes ₹ estimated value
    - Stores with TTL for expiry

    Phase 1: Advisory mode only — no broker integration.
    """

    @traced("execution.stage_order")
    async def stage_order(
        self,
        decision: GuardedDecision,
        portfolio: PortfolioCanonical,
        signal_price: float,
    ) -> StagedOrder | None:
        """
        Stage an order ticket for a BUY/SELL decision.

        Returns None for HOLD/WATCH decisions.
        """
        if decision.final_decision not in (Decision.BUY, Decision.SELL):
            return None

        action = decision.final_decision
        symbol = decision.signal_id.split("-")[0] if "-" in decision.signal_id else "UNKNOWN"

        # Extract symbol from portfolio context if available
        if decision.portfolio_context:
            # Use the symbol from the context
            pass

        # Use signal price for the ticker from the signal_id
        # Find the symbol from portfolio holdings or signal metadata
        for holding in portfolio.holdings:
            if holding.symbol.upper() in decision.signal_id.upper():
                symbol = holding.symbol
                break

        # ── Calculate quantity ──
        quantity = self._calculate_quantity(
            action=action,
            portfolio=portfolio,
            symbol=symbol,
            signal_price=signal_price,
            portfolio_impact=decision.portfolio_impact,
        )

        if quantity <= 0:
            return None

        # ── Calculate price ──
        # For BUY: limit slightly above current price
        # For SELL: limit slightly below current price
        buffer_pct = 0.005  # 0.5% buffer
        if action == Decision.BUY:
            price = round(signal_price * (1 + buffer_pct), 2)
        else:
            price = round(signal_price * (1 - buffer_pct), 2)

        estimated_value = round(quantity * price, 2)

        # ── Build staged order ──
        order = StagedOrder(
            order_ticket_id=f"order-{uuid.uuid4().hex[:12]}",
            action=action,
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type="LIMIT",
            estimated_value=estimated_value,
            valid_until=datetime.now(timezone.utc) + timedelta(seconds=decision.ttl_seconds),
            status=OrderStatus.STAGED,
        )

        # Store in memory
        _staged_orders[order.order_ticket_id] = order

        logger.info(
            "order_staged",
            order_ticket_id=order.order_ticket_id,
            action=action,
            symbol=symbol,
            quantity=quantity,
            price=price,
            estimated_value=estimated_value,
        )

        return order

    def _calculate_quantity(
        self,
        action: str,
        portfolio: PortfolioCanonical,
        symbol: str,
        signal_price: float,
        portfolio_impact,
    ) -> int:
        """Calculate the number of shares to buy/sell."""
        if signal_price <= 0:
            return 0

        if action == Decision.SELL:
            # Sell: reduce position — sell based on portfolio_impact.position_delta_pct
            current_holding = None
            for h in portfolio.holdings:
                if h.symbol == symbol:
                    current_holding = h
                    break

            if current_holding and current_holding.quantity > 0:
                if abs(portfolio_impact.position_delta_pct) > 0:
                    # Calculate shares from percentage
                    target_value_reduction = portfolio.total_value * abs(portfolio_impact.position_delta_pct) / 100
                    qty = int(target_value_reduction / signal_price)
                    return max(1, min(qty, int(current_holding.quantity)))
                else:
                    # Default: sell 20% of current position
                    return max(1, int(current_holding.quantity * 0.2))
            return 0

        elif action == Decision.BUY:
            # Buy: use cash_impact or calculate from position_delta_pct
            if abs(portfolio_impact.cash_impact) > 0:
                qty = int(abs(portfolio_impact.cash_impact) / signal_price)
            elif abs(portfolio_impact.position_delta_pct) > 0:
                target_value = portfolio.total_value * abs(portfolio_impact.position_delta_pct) / 100
                qty = int(target_value / signal_price)
            else:
                # Default: use 3% of portfolio value
                target_value = portfolio.total_value * 0.03
                qty = int(target_value / signal_price)

            # Don't exceed available cash
            max_affordable = int(portfolio.cash_balance / signal_price) if signal_price > 0 else 0
            return max(1, min(qty, max_affordable))

        return 0

    async def confirm_order(self, order_ticket_id: str) -> StagedOrder | None:
        """Confirm a staged order (advisory log — no actual execution in Phase 1)."""
        order = _staged_orders.get(order_ticket_id)
        if not order:
            return None

        if order.status != OrderStatus.STAGED:
            return order

        # Check if expired
        if datetime.now(timezone.utc) > order.valid_until:
            order.status = OrderStatus.EXPIRED
            return order

        order.status = OrderStatus.CONFIRMED
        logger.info(
            "order_confirmed",
            order_ticket_id=order_ticket_id,
            action=order.action,
            symbol=order.symbol,
            quantity=order.quantity,
            price=order.price,
        )
        return order

    async def dismiss_order(self, order_ticket_id: str) -> StagedOrder | None:
        """Dismiss/cancel a staged order."""
        order = _staged_orders.get(order_ticket_id)
        if not order:
            return None

        order.status = OrderStatus.CANCELLED
        logger.info("order_dismissed", order_ticket_id=order_ticket_id)
        return order

    def get_staged_orders(self) -> list[StagedOrder]:
        """Get all pending staged orders."""
        now = datetime.now(timezone.utc)
        result = []
        for order in _staged_orders.values():
            # Auto-expire
            if order.status == OrderStatus.STAGED and now > order.valid_until:
                order.status = OrderStatus.EXPIRED
            if order.status == OrderStatus.STAGED:
                result.append(order)
        return result

    def get_order(self, order_ticket_id: str) -> StagedOrder | None:
        """Get a specific staged order."""
        return _staged_orders.get(order_ticket_id)

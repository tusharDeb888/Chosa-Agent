"""
Publish Node — Emit guarded decision to streams for delivery.

Attaches:
- PortfolioContext (personalized exposure data)
- StagedOrder (pre-computed 1-click order ticket for BUY/SELL)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.core.enums import StreamTopic
from app.core.events import Event
from app.core.schemas import (
    GuardedDecision,
    AlertMessage,
    PortfolioContext,
)
from app.core.observability import get_logger, traced
from app.dependencies import get_redis
from app.streams.producer import StreamProducer
from app.orchestrator.state import AgentGraphState

logger = get_logger("orchestrator.nodes.publish")


def _build_portfolio_context(state: AgentGraphState) -> PortfolioContext | None:
    """Compute personalized portfolio context for the decision."""
    portfolio = state.get("portfolio")
    signal = state.get("signal")
    if not portfolio or not signal:
        return None

    from app.enrichment.filing_scraper import SECTOR_MAP

    symbol = signal.symbol
    sector = SECTOR_MAP.get(symbol, "Unknown")

    symbol_exposure_pct = 0.0
    symbol_value = 0.0
    symbol_quantity = 0.0
    sector_exposure_pct = 0.0
    sector_holdings = []

    for h in portfolio.holdings:
        pct = (h.market_value / portfolio.total_value * 100) if portfolio.total_value > 0 else 0
        h_sector = SECTOR_MAP.get(h.symbol, h.sector)

        if h.symbol == symbol:
            symbol_exposure_pct = pct
            symbol_value = h.market_value
            symbol_quantity = h.quantity

        if h_sector == sector:
            sector_exposure_pct += pct
            if h.symbol != symbol:
                sector_holdings.append(h.symbol)

    # Build personalized summary
    if symbol_value > 0:
        val_lakhs = symbol_value / 100000
        summary = (
            f"Your ₹{val_lakhs:.1f}L in {symbol} represents "
            f"{symbol_exposure_pct:.1f}% of your portfolio"
        )
        if sector_holdings:
            summary += f". You also hold {', '.join(sector_holdings)} in the {sector} sector."
    else:
        summary = f"You do not currently hold {symbol}."
        if sector_holdings:
            summary += f" But you have exposure to the {sector} sector via {', '.join(sector_holdings)}."

    return PortfolioContext(
        symbol_exposure_pct=round(symbol_exposure_pct, 2),
        symbol_value=round(symbol_value, 2),
        symbol_quantity=symbol_quantity,
        sector_name=sector,
        sector_exposure_pct=round(sector_exposure_pct, 2),
        sector_holdings=sector_holdings,
        personalized_summary=summary,
    )


@traced("node.publish")
async def publish_node(state: AgentGraphState) -> dict:
    """
    Publish the guarded decision to:
    1. agent.decisions stream (audit/replay)
    2. alerts.user_feed stream (real-time delivery)

    Enriches with:
    - PortfolioContext (personalized exposure data)
    - StagedOrder (pre-computed 1-click order for BUY/SELL)
    """
    guarded = state.get("guarded_decision")
    if not guarded:
        logger.error("publish_no_decision", signal_id=state.get("signal_id", ""))
        return {"error": "No guarded decision to publish"}

    redis_client = await get_redis()
    producer = StreamProducer(redis_client)

    signal = state["signal"]

    # ── Attach portfolio context ──
    portfolio_ctx = _build_portfolio_context(state)
    if portfolio_ctx:
        guarded.portfolio_context = portfolio_ctx

    # ── Stage order for BUY/SELL decisions ──
    staged_order = None
    if guarded.final_decision in ("BUY", "SELL"):
        try:
            from app.execution.service import OrderStagingService
            staging_service = OrderStagingService()
            portfolio = state.get("portfolio")
            if portfolio:
                staged_order = await staging_service.stage_order(
                    decision=guarded,
                    portfolio=portfolio,
                    signal_price=signal.price,
                )
                if staged_order:
                    guarded.staged_order = staged_order
        except Exception as e:
            logger.warning("order_staging_failed", error=str(e))

    # ── Publish to agent.decisions (audit trail) ──
    decision_event = Event(
        idempotency_key=Event.generate_decision_key(
            user_id=guarded.user_id,
            signal_id=guarded.signal_id,
        ),
        topic=StreamTopic.AGENT_DECISIONS,
        event_type="agent.decision",
        payload=guarded.model_dump(mode="json"),
        ticker=signal.symbol,
        signal_id=guarded.signal_id,
        user_id=guarded.user_id,
        tenant_id=guarded.tenant_id,
        workflow_id=guarded.workflow_id,
        trace_id=guarded.trace_id,
    )
    await producer.publish(decision_event)

    # ── Publish to alerts.user_feed (real-time delivery) ──
    alert = AlertMessage(
        alert_id=f"alert-{uuid.uuid4().hex[:12]}",
        user_id=guarded.user_id,
        decision=guarded,
        created_at=datetime.now(timezone.utc),
        ticker=signal.symbol,
        staged_order=staged_order,
    )

    alert_event = Event(
        idempotency_key=f"alert:{guarded.user_id}:{guarded.signal_id}",
        topic=StreamTopic.ALERTS_USER_FEED,
        event_type="alert.new",
        payload=alert.model_dump(mode="json"),
        ticker=signal.symbol,
        signal_id=guarded.signal_id,
        user_id=guarded.user_id,
        tenant_id=guarded.tenant_id,
    )
    await producer.publish(alert_event)

    logger.info(
        "decision_published",
        signal_id=guarded.signal_id,
        user_id=guarded.user_id,
        final_decision=guarded.final_decision,
        confidence=guarded.confidence,
        has_portfolio_context=portfolio_ctx is not None,
        has_staged_order=staged_order is not None,
    )

    return {}

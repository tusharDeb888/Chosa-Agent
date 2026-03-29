"""
Orchestrator Worker — Consumes qualified signals and runs the LangGraph pipeline.

Fan-out: for each qualified signal, find impacted users via portfolio_positions,
then execute the graph once per (user_id, signal_id).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from app.config import get_settings
from app.core.enums import AgentState, StreamTopic
from app.core.events import Event
from app.core.schemas import (
    PolicyConstraints,
    PortfolioCanonical,
    PortfolioHolding,
    QualifiedSignal,
    RiskProfile,
)
from app.core.observability import get_logger
from app.dependencies import get_redis
from app.db.engine import get_session_factory
from app.db.repositories import PositionRepository, PortfolioRepository, UserRepository, ProcessedEventRepository
from app.orchestrator.graph import agent_graph
from app.streams.consumer import StreamConsumer
from app.streams.dlq import DeadLetterQueue

logger = get_logger("orchestrator.worker")


async def start_orchestrator_worker() -> None:
    """Start the orchestrator consumer worker."""
    settings = get_settings()
    redis_client = await get_redis()
    consumer = StreamConsumer(redis_client, StreamTopic.SIGNALS_QUALIFIED)
    dlq = DeadLetterQueue(redis_client)
    semaphore = asyncio.Semaphore(settings.orchestrator_max_concurrent_tasks)

    async def handle_event(event: Event) -> None:
        """Fan-out: find impacted users and run graph for each."""
        agent_state = await redis_client.get("agent:state") or AgentState.PAUSED
        if agent_state != AgentState.RUNNING:
            return

        signal = QualifiedSignal(**event.payload)

        # Find impacted users via portfolio_positions
        session_factory = get_session_factory()
        async with session_factory() as session:
            pos_repo = PositionRepository(session)
            user_repo = UserRepository(session)
            portfolio_repo = PortfolioRepository(session)
            processed_repo = ProcessedEventRepository(session)

            # Get all users holding this symbol
            positions = await pos_repo.get_users_by_symbol(signal.symbol)

            if not positions:
                # No positions — check if we have any active users at all
                # In Phase 1, run for all active users for demo purposes
                active_users = await user_repo.get_active_users()
                user_ids = [u.id for u in active_users[:5]]  # Cap at 5 for Phase 1
            else:
                user_ids = list(set(p.user_id for p in positions))

            # Execute graph for each impacted user
            tasks = []
            for user_id in user_ids:
                # Idempotency check
                decision_key = Event.generate_decision_key(
                    user_id=str(user_id),
                    signal_id=signal.signal_id,
                )
                if await processed_repo.is_processed(decision_key):
                    logger.debug(
                        "duplicate_skipped",
                        user_id=str(user_id),
                        signal_id=signal.signal_id,
                    )
                    continue

                task = asyncio.create_task(
                    _run_graph_for_user(
                        signal=signal,
                        user_id=user_id,
                        session_factory=session_factory,
                        semaphore=semaphore,
                    )
                )
                tasks.append(task)

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def handle_error(event: Event, error: Exception) -> None:
        event.attempt += 1
        if await dlq.should_dlq(event):
            await dlq.route_to_dlq(event, error, StreamTopic.SIGNALS_QUALIFIED)

    await consumer.run(handler=handle_event, on_error=handle_error)


async def _run_graph_for_user(
    signal: QualifiedSignal,
    user_id,
    session_factory,
    semaphore: asyncio.Semaphore,
) -> None:
    """Execute the LangGraph pipeline for a single user."""
    async with semaphore:
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"

        try:
            async with session_factory() as session:
                user_repo = UserRepository(session)
                portfolio_repo = PortfolioRepository(session)
                processed_repo = ProcessedEventRepository(session)

                user = await user_repo.get_by_id(user_id)
                if not user or user.agent_state != AgentState.RUNNING:
                    return

                # Build portfolio
                portfolio_record = await portfolio_repo.get_by_user(user_id)
                portfolio = PortfolioCanonical(
                    user_id=str(user_id),
                    mode=user.portfolio_mode,
                    total_value=portfolio_record.total_value if portfolio_record else 0.0,
                    cash_balance=portfolio_record.cash_balance if portfolio_record else 0.0,
                )

                if portfolio_record and portfolio_record.holdings:
                    for h in portfolio_record.holdings.get("items", []):
                        portfolio.holdings.append(PortfolioHolding(**h))

                # Build risk profile
                risk_profile = RiskProfile(
                    risk_tolerance=user.risk_tolerance,
                )

                # Build policy constraints
                policy = PolicyConstraints(**(user.policy_constraints or {}))

                # ── Run the graph ──
                initial_state = {
                    "signal": signal,
                    "user_id": str(user_id),
                    "tenant_id": user.tenant_id,
                    "portfolio": portfolio,
                    "risk_profile": risk_profile,
                    "policy_constraints": policy,
                    "daily_action_count": 0,
                    "workflow_id": workflow_id,
                    "trace_id": f"trace-{uuid.uuid4().hex[:12]}",
                    "signal_id": signal.signal_id,
                    "retry_count": 0,
                }

                result = await agent_graph.ainvoke(initial_state)

                # Mark as processed (idempotency)
                decision_key = Event.generate_decision_key(
                    user_id=str(user_id),
                    signal_id=signal.signal_id,
                )
                await processed_repo.mark_processed(
                    idempotency_key=decision_key,
                    event_type="agent.decision",
                    signal_id=signal.signal_id,
                    user_id=str(user_id),
                )
                await session.commit()

                logger.info(
                    "graph_execution_complete",
                    workflow_id=workflow_id,
                    user_id=str(user_id),
                    signal_id=signal.signal_id,
                    decision=result.get("guarded_decision", {}).get("final_decision", "unknown") if isinstance(result.get("guarded_decision"), dict) else getattr(result.get("guarded_decision"), "final_decision", "unknown"),
                )

        except Exception as e:
            logger.error(
                "graph_execution_failed",
                workflow_id=workflow_id,
                user_id=str(user_id),
                signal_id=signal.signal_id,
                error=str(e),
            )

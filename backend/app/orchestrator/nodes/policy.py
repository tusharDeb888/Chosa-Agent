"""
Policy Check Node — Runs the policy guardrail engine post-LLM.
"""

from __future__ import annotations

from app.core.schemas import EvidencePack, PolicyConstraints, DecisionOutput, PortfolioImpact
from app.core.enums import Decision
from app.core.observability import get_logger, traced
from app.policy.engine import PolicyEngine
from app.orchestrator.state import AgentGraphState

logger = get_logger("orchestrator.nodes.policy")

_policy_engine: PolicyEngine | None = None


def _get_policy_engine() -> PolicyEngine:
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine


@traced("node.policy_check")
async def policy_check_node(state: AgentGraphState) -> dict:
    """
    Validate the LLM decision against user policy constraints.

    Non-compliant BUY/SELL decisions are downgraded to WATCH.
    """
    engine = _get_policy_engine()

    decision = state.get("decision")
    if not decision:
        # If synthesis failed, create a minimal WATCH decision
        decision = DecisionOutput(
            decision=Decision.WATCH,
            confidence=10,
            rationale="No decision available — synthesis stage failed.",
            risk_flags=["SYNTHESIS_FAILED"],
            portfolio_impact=PortfolioImpact(),
            ttl_seconds=60,
        )

    signal = state["signal"]
    portfolio = state["portfolio"]
    evidence = state.get("evidence_pack", EvidencePack(degraded_context=True))
    constraints = state.get("policy_constraints", PolicyConstraints())
    user_id = state.get("user_id", "")
    tenant_id = state.get("tenant_id", "default")
    daily_count = state.get("daily_action_count", 0)

    guarded = await engine.enforce(
        decision=decision,
        signal=signal,
        portfolio=portfolio,
        constraints=constraints,
        evidence=evidence,
        user_id=user_id,
        tenant_id=tenant_id,
        daily_action_count=daily_count,
        workflow_id=state.get("workflow_id", ""),
        trace_id=state.get("trace_id", ""),
    )

    logger.info(
        "policy_check_complete",
        signal_id=signal.signal_id,
        original=guarded.original_decision,
        final=guarded.final_decision,
        policy_passed=guarded.policy_passed,
        violations=guarded.policy_reason_codes,
    )

    return {"guarded_decision": guarded}

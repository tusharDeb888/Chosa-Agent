"""
Synthesize Node — LLM decision generation via the Decision Engine.
"""

from __future__ import annotations

from app.core.schemas import PolicyConstraints, RiskProfile
from app.core.observability import get_logger, traced
from app.decision.engine import DecisionEngine
from app.orchestrator.state import AgentGraphState

logger = get_logger("orchestrator.nodes.synthesize")

_engine: DecisionEngine | None = None


def _get_engine() -> DecisionEngine:
    global _engine
    if _engine is None:
        _engine = DecisionEngine()
    return _engine


@traced("node.synthesize")
async def synthesize_node(state: AgentGraphState) -> dict:
    """
    Call the Decision Engine (Groq LLM) to produce a recommendation.

    Input bundle: signal + evidence + portfolio + risk_profile + policy_constraints
    Output: DecisionOutput (schema-validated)
    """
    engine = _get_engine()

    signal = state["signal"]
    portfolio = state["portfolio"]
    evidence = state.get("evidence_pack")
    risk_profile = state.get("risk_profile", RiskProfile())
    policy_constraints = state.get("policy_constraints", PolicyConstraints())

    if evidence is None:
        from app.core.schemas import EvidencePack
        evidence = EvidencePack(degraded_context=True)

    try:
        decision = await engine.synthesize(
            signal=signal,
            portfolio=portfolio,
            evidence=evidence,
            risk_profile=risk_profile,
            policy=policy_constraints,
        )

        logger.info(
            "synthesis_complete",
            decision=decision.decision,
            confidence=decision.confidence,
            signal_id=signal.signal_id,
        )

        return {"decision": decision}

    except Exception as e:
        logger.error(
            "synthesis_failed",
            error=str(e),
            signal_id=signal.signal_id,
        )
        return {"error": f"Synthesis failed: {str(e)}"}

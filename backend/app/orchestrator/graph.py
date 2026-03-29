"""
LangGraph Agent Graph — Stateful decision pipeline.

Graph: START -> enrich -> synthesize -> policy_check -> publish -> END
                                           ↓ (violation)
                                    downgrade_to_watch -> publish -> END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.orchestrator.state import AgentGraphState
from app.orchestrator.nodes.enrich import enrich_node
from app.orchestrator.nodes.synthesize import synthesize_node
from app.orchestrator.nodes.policy import policy_check_node
from app.orchestrator.nodes.publish import publish_node
from app.core.observability import get_logger

logger = get_logger("orchestrator.graph")


def should_publish(state: AgentGraphState) -> str:
    """Conditional edge: route based on policy check result."""
    if state.get("error"):
        return "publish"  # Publish error/degraded result anyway
    guarded = state.get("guarded_decision")
    if guarded and not guarded.policy_passed:
        logger.info(
            "policy_violation_detected",
            signal_id=state.get("signal_id", ""),
            violations=guarded.policy_reason_codes,
        )
    # Always publish — the guarded_decision already contains
    # the downgraded decision if policy failed
    return "publish"


def build_agent_graph() -> StateGraph:
    """
    Construct the LangGraph state machine for the decision pipeline.

    Each node has exactly one responsibility:
    - enrich: gather evidence from web + vector memory
    - synthesize: LLM decision generation
    - policy_check: validate against user constraints
    - publish: emit the guarded decision
    """
    graph = StateGraph(AgentGraphState)

    # ── Add nodes ──
    graph.add_node("enrich", enrich_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("policy_check", policy_check_node)
    graph.add_node("publish", publish_node)

    # ── Define edges ──
    graph.set_entry_point("enrich")
    graph.add_edge("enrich", "synthesize")
    graph.add_edge("synthesize", "policy_check")
    graph.add_conditional_edges(
        "policy_check",
        should_publish,
        {"publish": "publish"},
    )
    graph.add_edge("publish", END)

    return graph


# Compiled graph instance (reusable)
agent_graph = build_agent_graph().compile()

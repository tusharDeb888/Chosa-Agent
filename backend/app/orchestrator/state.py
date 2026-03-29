"""
Orchestrator State — TypedDict defining the LangGraph state schema.
"""

from __future__ import annotations

from typing import Optional, TypedDict

from app.core.schemas import (
    DecisionOutput,
    EvidencePack,
    GuardedDecision,
    PolicyConstraints,
    PortfolioCanonical,
    QualifiedSignal,
    RiskProfile,
)


class AgentGraphState(TypedDict, total=False):
    """
    LangGraph state schema for the decision pipeline.

    This is the single source of truth flowing through the graph.
    Strongly typed and minimal per LangGraph best practices.
    """

    # ── Input (set at graph entry) ──
    signal: QualifiedSignal
    user_id: str
    tenant_id: str
    portfolio: PortfolioCanonical
    risk_profile: RiskProfile
    policy_constraints: PolicyConstraints
    daily_action_count: int

    # ── Computed by nodes ──
    evidence_pack: Optional[EvidencePack]
    decision: Optional[DecisionOutput]
    guarded_decision: Optional[GuardedDecision]

    # ── Control / Metadata ──
    error: Optional[str]
    retry_count: int
    workflow_id: str
    trace_id: str
    signal_id: str

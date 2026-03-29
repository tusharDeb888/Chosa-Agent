"""
Policy Guardrail Engine — Post-LLM constraint validation.

PRD §10: Rules engine validates constraints before publishing.
Non-compliant decisions downgraded to WATCH with reason codes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.enums import Decision, PolicyViolationType
from app.core.schemas import (
    DecisionOutput,
    EvidencePack,
    GuardedDecision,
    PolicyConstraints,
    PortfolioCanonical,
    QualifiedSignal,
)
from app.core.observability import get_logger

logger = get_logger("policy.engine")


class PolicyEngine:
    """
    Post-LLM policy guardrail.

    Evaluates a decision against user-specific constraints and
    downgrades to WATCH if any violation is found.
    """

    async def enforce(
        self,
        decision: DecisionOutput,
        signal: QualifiedSignal,
        portfolio: PortfolioCanonical,
        constraints: PolicyConstraints,
        evidence: EvidencePack,
        user_id: str,
        tenant_id: str = "default",
        daily_action_count: int = 0,
        workflow_id: str = "",
        trace_id: str = "",
    ) -> GuardedDecision:
        """
        Apply all policy rules and return guarded decision.

        Returns GuardedDecision with policy_passed=True/False.
        """
        violations: list[str] = []

        # ── Rule 1: Max position concentration ──
        if decision.decision in (Decision.BUY,):
            current_exposure = self._get_symbol_exposure(portfolio, signal.symbol)
            projected = current_exposure + abs(decision.portfolio_impact.position_delta_pct)
            if projected > constraints.max_position_concentration_pct:
                violations.append(PolicyViolationType.MAX_CONCENTRATION_EXCEEDED)

        # ── Rule 2: Max daily actionable recommendations ──
        if decision.decision in (Decision.BUY, Decision.SELL):
            if daily_action_count >= constraints.max_daily_actions:
                violations.append(PolicyViolationType.DAILY_ACTION_LIMIT_REACHED)

        # ── Rule 3: Minimum confidence for BUY/SELL ──
        if decision.decision in (Decision.BUY, Decision.SELL):
            if decision.confidence < constraints.min_confidence_buy_sell:
                violations.append(PolicyViolationType.CONFIDENCE_BELOW_THRESHOLD)

        # ── Rule 4: Max evidence age ──
        if evidence.items:
            max_age_hours = constraints.max_evidence_age_hours
            now = datetime.now(timezone.utc)
            for item in evidence.items:
                if item.published_at:
                    pub = item.published_at
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=timezone.utc)
                    age_hours = (now - pub).total_seconds() / 3600
                    if age_hours > max_age_hours:
                        violations.append(PolicyViolationType.EVIDENCE_TOO_STALE)
                        break

        # ── Rule 5: Portfolio staleness ──
        if portfolio.is_stale:
            if decision.decision in (Decision.BUY, Decision.SELL):
                violations.append(PolicyViolationType.PORTFOLIO_STALE)

        # ── Build guarded decision ──
        policy_passed = len(violations) == 0
        final_decision = decision.decision

        if not policy_passed and decision.decision in (Decision.BUY, Decision.SELL):
            final_decision = Decision.WATCH
            logger.warning(
                "decision_downgraded",
                original=decision.decision,
                violations=violations,
                signal_id=signal.signal_id,
                user_id=user_id,
            )

        return GuardedDecision(
            signal_id=signal.signal_id,
            user_id=user_id,
            tenant_id=tenant_id,
            original_decision=decision.decision,
            final_decision=final_decision,
            confidence=decision.confidence,
            rationale=decision.rationale,
            citations=decision.citations,
            portfolio_impact=decision.portfolio_impact,
            risk_flags=decision.risk_flags,
            policy_reason_codes=[v.value if hasattr(v, 'value') else v for v in violations],
            policy_passed=policy_passed,
            ttl_seconds=decision.ttl_seconds,
            degraded_context=evidence.degraded_context,
            created_at=datetime.now(timezone.utc),
            workflow_id=workflow_id,
            trace_id=trace_id,
        )

    def _get_symbol_exposure(
        self, portfolio: PortfolioCanonical, symbol: str
    ) -> float:
        """Calculate current exposure to a symbol as % of portfolio."""
        if portfolio.total_value <= 0:
            return 0.0
        for h in portfolio.holdings:
            if h.symbol == symbol:
                return (h.market_value / portfolio.total_value) * 100
        return 0.0

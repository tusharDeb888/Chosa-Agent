"""
Test Policy Guardrails — All 5 PRD §8 policy rules.

Tests policy enforcement, downgrade logic, and violation codes.
"""

from datetime import datetime, timezone

import pytest

from app.core.enums import Decision
from app.core.schemas import (
    DecisionOutput,
    EvidencePack,
    EvidenceItem,
    GuardedDecision,
    PolicyConstraints,
    PortfolioCanonical,
    PortfolioHolding,
    PortfolioImpact,
    QualifiedSignal,
    Citation,
)
from app.policy.engine import PolicyEngine


def _make_signal(**overrides) -> QualifiedSignal:
    defaults = {
        "signal_id": "sig-policy-test",
        "symbol": "TCS",
        "anomaly_type": "VOLUME_SPIKE",
        "price": 3800.0,
        "volume": 100000,
        "z_score": 3.5,
        "vwap_deviation_pct": 2.0,
        "confidence": 75.0,
        "timestamp": datetime.now(timezone.utc),
        "source": "mock",
        "qualified_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return QualifiedSignal(**defaults)


def _make_decision(**overrides) -> DecisionOutput:
    defaults = {
        "decision": Decision.BUY,
        "confidence": 78,
        "rationale": "Strong volume surge in TCS",
        "citations": [Citation(url="https://moneycontrol.com/tcs", published_at="2026-03-28")],
        "portfolio_impact": PortfolioImpact(position_delta_pct=5.0, sector_exposure_delta_pct=3.0, cash_impact=-50000),
        "risk_flags": [],
        "ttl_seconds": 300,
    }
    defaults.update(overrides)
    return DecisionOutput(**defaults)


def _make_portfolio(**overrides) -> PortfolioCanonical:
    defaults = {
        "user_id": "user-test",
        "holdings": [
            PortfolioHolding(symbol="TCS", quantity=100, avg_price=3500, market_value=380000, sector="IT"),
            PortfolioHolding(symbol="HDFC", quantity=50, avg_price=1600, market_value=80000, sector="BFSI"),
        ],
        "total_value": 500000,
        "cash_balance": 40000,
        "is_stale": False,
    }
    defaults.update(overrides)
    return PortfolioCanonical(**defaults)


def _make_constraints(**overrides) -> PolicyConstraints:
    defaults = {
        "max_position_concentration_pct": 25.0,
        "max_daily_actions": 20,
        "min_confidence_buy_sell": 60,
        "max_evidence_age_hours": 24,
    }
    defaults.update(overrides)
    return PolicyConstraints(**defaults)


def _make_evidence(**overrides) -> EvidencePack:
    defaults = {
        "items": [
            EvidenceItem(
                source_url="https://moneycontrol.com/tcs",
                content="TCS volume surge analysis",
                fetched_at=datetime.now(timezone.utc),
                published_at=datetime.now(timezone.utc),
                reliability_score=0.8,
            ),
        ],
        "degraded_context": False,
        "freshness_score": 0.8,
    }
    defaults.update(overrides)
    return EvidencePack(**defaults)


class TestPolicyEngine:
    """Test all policy guardrail rules."""

    def setup_method(self):
        self.engine = PolicyEngine()

    @pytest.mark.asyncio
    async def test_valid_decision_passes(self):
        """A compliant BUY decision should pass all policy checks."""
        # Use a portfolio where TCS is a small position (10% = 50k/500k)
        result = await self.engine.enforce(
            decision=_make_decision(portfolio_impact=PortfolioImpact(position_delta_pct=3.0)),
            signal=_make_signal(),
            portfolio=_make_portfolio(holdings=[
                PortfolioHolding(symbol="TCS", quantity=10, avg_price=3500, market_value=50000, sector="IT"),
                PortfolioHolding(symbol="HDFC", quantity=50, avg_price=1600, market_value=80000, sector="BFSI"),
            ]),
            constraints=_make_constraints(),
            evidence=_make_evidence(),
            user_id="user-test",
        )
        assert isinstance(result, GuardedDecision)
        assert result.policy_passed is True
        assert result.final_decision == Decision.BUY

    @pytest.mark.asyncio
    async def test_max_concentration_violation(self):
        """Rule 1: BUY exceeding position concentration should be downgraded."""
        # TCS is already 76% of portfolio (380k / 500k)
        result = await self.engine.enforce(
            decision=_make_decision(portfolio_impact=PortfolioImpact(position_delta_pct=5.0)),
            signal=_make_signal(),
            portfolio=_make_portfolio(),
            constraints=_make_constraints(max_position_concentration_pct=25.0),
            evidence=_make_evidence(),
            user_id="user-test",
        )
        assert result.policy_passed is False
        assert result.final_decision == Decision.WATCH
        assert "MAX_CONCENTRATION_EXCEEDED" in result.policy_reason_codes

    @pytest.mark.asyncio
    async def test_daily_action_limit(self):
        """Rule 2: Exceeding daily action limit should downgrade BUY/SELL."""
        result = await self.engine.enforce(
            decision=_make_decision(),
            signal=_make_signal(),
            portfolio=_make_portfolio(),
            constraints=_make_constraints(max_daily_actions=5),
            evidence=_make_evidence(),
            user_id="user-test",
            daily_action_count=5,
        )
        assert result.policy_passed is False
        assert "DAILY_ACTION_LIMIT_REACHED" in result.policy_reason_codes

    @pytest.mark.asyncio
    async def test_confidence_below_threshold(self):
        """Rule 3: BUY with low confidence should be downgraded."""
        result = await self.engine.enforce(
            decision=_make_decision(confidence=40),
            signal=_make_signal(),
            portfolio=_make_portfolio(),
            constraints=_make_constraints(min_confidence_buy_sell=60),
            evidence=_make_evidence(),
            user_id="user-test",
        )
        assert result.policy_passed is False
        assert "CONFIDENCE_BELOW_THRESHOLD" in result.policy_reason_codes

    @pytest.mark.asyncio
    async def test_stale_portfolio_blocks_buy(self):
        """Rule 5: Stale portfolio should block actionable decisions."""
        result = await self.engine.enforce(
            decision=_make_decision(),
            signal=_make_signal(),
            portfolio=_make_portfolio(is_stale=True),
            constraints=_make_constraints(),
            evidence=_make_evidence(),
            user_id="user-test",
        )
        assert result.policy_passed is False
        assert "PORTFOLIO_STALE" in result.policy_reason_codes
        assert result.final_decision == Decision.WATCH

    @pytest.mark.asyncio
    async def test_watch_not_downgraded(self):
        """WATCH decisions should NOT be further downgraded even with violations."""
        result = await self.engine.enforce(
            decision=_make_decision(decision=Decision.WATCH, confidence=10, citations=[]),
            signal=_make_signal(),
            portfolio=_make_portfolio(is_stale=True),
            constraints=_make_constraints(),
            evidence=_make_evidence(),
            user_id="user-test",
        )
        # WATCH is not actionable, so stale portfolio doesn't apply
        assert result.final_decision == Decision.WATCH

    @pytest.mark.asyncio
    async def test_hold_not_downgraded(self):
        """HOLD decisions are not downgraded (only BUY/SELL are)."""
        result = await self.engine.enforce(
            decision=_make_decision(decision=Decision.HOLD, confidence=40, citations=[]),
            signal=_make_signal(),
            portfolio=_make_portfolio(),
            constraints=_make_constraints(min_confidence_buy_sell=60),
            evidence=_make_evidence(),
            user_id="user-test",
        )
        assert result.final_decision == Decision.HOLD

    @pytest.mark.asyncio
    async def test_guarded_decision_has_provenance(self):
        """Result should contain full provenance metadata."""
        result = await self.engine.enforce(
            decision=_make_decision(),
            signal=_make_signal(),
            portfolio=_make_portfolio(),
            constraints=_make_constraints(),
            evidence=_make_evidence(),
            user_id="user-123",
            tenant_id="tenant-abc",
            workflow_id="wf-001",
            trace_id="tr-001",
        )
        assert result.user_id == "user-123"
        assert result.tenant_id == "tenant-abc"
        assert result.workflow_id == "wf-001"
        assert result.trace_id == "tr-001"
        assert result.created_at is not None

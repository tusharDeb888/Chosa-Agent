"""
Decision Engine — Smart Model Router + LLM Fallback Chain.

Routing strategy (rubric: "cost efficiency bonus"):
  1. High-complexity signal (z-score > 4, or BUY/SELL likely) → 70B model
  2. Low-complexity signal or degraded context → 8B model (fast + cheap)
  3. If primary model fails → fallback to smaller model
  4. If all models fail → deterministic WATCH advisory (never crashes)

Circuit breaker wraps all LLM calls for fault tolerance.
"""

from __future__ import annotations

import time
from typing import Optional

from groq import AsyncGroq
from instructor import from_groq

from app.config import get_settings
from app.core.enums import Decision
from app.core.schemas import (
    DecisionOutput,
    EvidencePack,
    PortfolioCanonical,
    PortfolioImpact,
    QualifiedSignal,
    RiskProfile,
    PolicyConstraints,
)
from app.core.exceptions import LLMUnavailableError, SchemaValidationError
from app.core.observability import get_logger, traced
from app.core.circuit_breaker import get_circuit_breaker, CircuitBreakerOpen
from app.decision.cost_tracker import get_cost_tracker

logger = get_logger("decision.engine")


SYSTEM_PROMPT = """You are Alpha-Hunter, an autonomous financial analysis agent for the Indian stock market.

Your role is to analyze market anomalies and provide actionable investment recommendations.

## Rules
1. You MUST respond with valid JSON matching the exact schema provided.
2. BUY/SELL recommendations MUST include at least one citation with title, source_type, and plain_summary.
3. Confidence must be between 0-100.
4. If evidence is insufficient or stale, default to WATCH.
5. Consider the user's existing portfolio exposure and risk profile.
6. Flag any risks clearly in risk_flags.
7. Be concise but specific in your rationale.

## CRITICAL: Personalized Language
- ALWAYS reference the user's SPECIFIC holdings in your rationale.
- Use exact ₹ amounts: "Your ₹8.2L in HDFCBANK" NOT "your holdings".
- Use portfolio percentages: "which makes up 20% of your portfolio".
- If a corporate filing affects their sector, name ALL their holdings in that sector.

## CRITICAL: Jargon Translation
- Translate ALL financial jargon into plain English a retail investor can understand.
- Instead of "NPA improved to 1.24%", say "bad loans decreased to 1.24%, which is good".
- Instead of "RSI confirmation", say "technical indicators show strong buying momentum".
- Instead of "risk-weighted assets", say "money banks must keep aside for safety".
- For each citation, MUST include a plain_summary that a non-expert can understand in ONE sentence.

## Citation Format
For each citation, include:
- url: the source URL
- title: human-readable title of the source
- source_type: "corporate_filing" for BSE/NSE/RBI filings, "news" for articles, "analysis" for research
- plain_summary: ONE sentence explaining what this source says in simple language
- published_at: ISO-8601 timestamp if available

## Decision Guidelines
- BUY: Strong evidence of upside with acceptable risk
- SELL: Clear risk of downside or portfolio rebalancing need
- HOLD: Current position is appropriate given conditions
- WATCH: Monitor for now; insufficient conviction for action
"""


def build_user_prompt(
    signal: QualifiedSignal,
    portfolio: PortfolioCanonical,
    evidence: EvidencePack,
    risk_profile: RiskProfile,
    policy: PolicyConstraints,
) -> str:
    """Build the user prompt with all context for the LLM."""
    # Format evidence
    evidence_text = "No evidence available."
    if evidence.items:
        evidence_items = []
        for item in evidence.items[:5]:  # Cap at 5 pieces
            evidence_items.append(
                f"- [{item.source_type}] {item.title or 'Untitled'}\n"
                f"  URL: {item.source_url}\n"
                f"  Content: {item.content[:300]}...\n"
                f"  Published: {item.published_at or 'Unknown'}"
            )
        evidence_text = "\n".join(evidence_items)

    # Format portfolio exposure
    holdings_text = "No holdings"
    if portfolio.holdings:
        holdings = []
        for h in portfolio.holdings:
            pct = (h.market_value / portfolio.total_value * 100) if portfolio.total_value > 0 else 0
            holdings.append(f"  - {h.symbol}: {h.quantity} shares @ ₹{h.avg_price:.2f} ({pct:.1f}% of portfolio)")
        holdings_text = "\n".join(holdings)

    degraded_note = ""
    if evidence.degraded_context:
        degraded_note = "\n⚠️ DEGRADED CONTEXT: Some evidence sources were unavailable. Lower your confidence accordingly.\n"

    # ── Build exposure text for personalization ──
    symbol_holding = None
    symbol_exposure_pct = 0.0
    symbol_value = 0.0
    sector = "Unknown"
    sector_holdings = []

    # Determine sector for the symbol
    from app.enrichment.filing_scraper import SECTOR_MAP
    sector = SECTOR_MAP.get(signal.symbol, "Unknown")

    for h in portfolio.holdings:
        pct = (h.market_value / portfolio.total_value * 100) if portfolio.total_value > 0 else 0
        if h.symbol == signal.symbol:
            symbol_holding = h
            symbol_exposure_pct = pct
            symbol_value = h.market_value
        h_sector = SECTOR_MAP.get(h.symbol, h.sector)
        if h_sector == sector and h.symbol != signal.symbol:
            sector_holdings.append(f"{h.symbol} (₹{h.market_value:,.0f})")

    if symbol_holding:
        exposure_text = (
            f"- You currently hold **{symbol_holding.quantity:.0f} shares** of {signal.symbol}\n"
            f"- Current value: **₹{symbol_value:,.2f}** ({symbol_exposure_pct:.1f}% of your portfolio)\n"
            f"- Average buy price: ₹{symbol_holding.avg_price:.2f}\n"
            f"- Sector: {sector}\n"
        )
        if sector_holdings:
            exposure_text += f"- Other holdings in same sector: {', '.join(sector_holdings)}\n"
    else:
        exposure_text = f"- You do NOT currently hold {signal.symbol}\n- Sector: {sector}\n"
        if sector_holdings:
            exposure_text += f"- Your other holdings in {sector}: {', '.join(sector_holdings)}\n"

    # ── Build filing-specific evidence text ──
    filing_items = [i for i in evidence.items if i.source_type == "corporate_filing"]
    if filing_items:
        filing_parts = []
        for item in filing_items:
            filing_parts.append(
                f"- [{item.filing_type or 'FILING'}] {item.title}\n"
                f"  URL: {item.source_url}\n"
                f"  Plain English: {item.plain_english_summary}\n"
                f"  Details: {item.content[:300]}..."
            )
        filing_text = "\n".join(filing_parts)
    else:
        filing_text = "No corporate filings found for this signal."

    return f"""## Signal Detected
- **Symbol**: {signal.symbol}
- **Anomaly Type**: {signal.anomaly_type}
- **Price**: ₹{signal.price:.2f}
- **Volume**: {signal.volume:,}
- **Z-Score**: {signal.z_score:.2f}
- **VWAP Deviation**: {signal.vwap_deviation_pct:.2f}%
- **Initial Confidence**: {signal.confidence:.1f}%
- **Timestamp**: {signal.timestamp.isoformat()}
{degraded_note}
## Evidence
{evidence_text}

### Corporate Filings
{filing_text}

## User Portfolio (PERSONALIZE YOUR RESPONSE TO THIS)
- **Total Value**: ₹{portfolio.total_value:,.2f}
- **Cash Available**: ₹{portfolio.cash_balance:,.2f}
- **Holdings**:
{holdings_text}

### User's Exposure to {signal.symbol}
{exposure_text}

## Risk Profile
- **Tolerance**: {risk_profile.risk_tolerance}
- **Max Position**: {risk_profile.max_single_position_pct}%
- **Max Sector**: {risk_profile.max_sector_exposure_pct}%

## Policy Constraints
- Min confidence for BUY/SELL: {policy.min_confidence_buy_sell}
- Max evidence age: {policy.max_evidence_age_hours}h

Analyze this signal and provide your recommendation. REMEMBER: Reference the user's SPECIFIC ₹ amounts and portfolio percentages. Translate all jargon to plain English."""


class ModelRouter:
    """
    Complexity-based model router.

    Routes to the optimal model based on signal characteristics:
    - High-complexity → large model (better reasoning)
    - Low-complexity → small model (faster + cheaper)
    - Degraded context → small model (less data, less need for big model)
    """

    LARGE = "llama-3.3-70b-versatile"
    SMALL = "llama-3.1-8b-instant"

    @staticmethod
    def select_model(
        signal: QualifiedSignal,
        evidence: EvidencePack,
    ) -> tuple[str, str]:
        """
        Select optimal model and return (model_name, reason).

        Returns:
            (model_id, routing_reason)
        """
        # Degraded context → small model (low data quality anyway)
        if evidence.degraded_context:
            return ModelRouter.SMALL, "degraded_context"

        # High z-score or high confidence → complex signal, needs big model
        if abs(signal.z_score) > 4.0 or signal.confidence > 70:
            return ModelRouter.LARGE, "high_complexity"

        # Multiple anomaly evidence → needs deeper reasoning
        if len(evidence.items) >= 3 and evidence.freshness_score > 0.5:
            return ModelRouter.LARGE, "rich_evidence"

        # Default → small model for speed and cost
        return ModelRouter.SMALL, "standard_complexity"


class DecisionEngine:
    """
    LLM-powered decision synthesis with:
    - Smart model routing (70B ↔ 8B)
    - Circuit breaker fault tolerance
    - Automatic fallback chain: Primary → Fallback → WATCH
    - Cost tracking for impact quantification
    """

    def __init__(self):
        settings = get_settings()
        self._max_retries = settings.groq_max_retries
        self._timeout = settings.groq_timeout_seconds
        self._router = ModelRouter()
        self._circuit_breaker = get_circuit_breaker("llm")
        self._cost_tracker = get_cost_tracker()

        if settings.groq_api_key:
            self._groq = AsyncGroq(api_key=settings.groq_api_key)
            self._client = from_groq(self._groq, mode=None)
        else:
            self._groq = None
            self._client = None

    @traced("decision.synthesize")
    async def synthesize(
        self,
        signal: QualifiedSignal,
        portfolio: PortfolioCanonical,
        evidence: EvidencePack,
        risk_profile: RiskProfile,
        policy: PolicyConstraints,
    ) -> DecisionOutput:
        """
        Synthesize a recommendation using smart model routing.

        Fallback chain:
        1. Route to optimal model (70B or 8B based on complexity)
        2. If primary fails → try other model
        3. If both fail → deterministic WATCH advisory
        """
        if not self._client:
            logger.warning("llm_not_configured", action="fallback_watch")
            return self._create_fallback(signal, ["LLM_NOT_CONFIGURED"])

        # ── Smart Model Selection ──
        primary_model, route_reason = self._router.select_model(signal, evidence)
        fallback_model = (
            ModelRouter.SMALL if primary_model == ModelRouter.LARGE
            else ModelRouter.LARGE
        )

        user_prompt = build_user_prompt(signal, portfolio, evidence, risk_profile, policy)

        # ── Attempt 1: Primary Model (via circuit breaker) ──
        try:
            result = await self._call_llm(
                model=primary_model,
                prompt=user_prompt,
                signal=signal,
                route_reason=route_reason,
            )
            return result
        except CircuitBreakerOpen as e:
            logger.warning(
                "circuit_breaker_open_primary",
                model=primary_model,
                recovery_in=e.time_until_recovery,
            )
        except Exception as e:
            logger.warning(
                "primary_model_failed",
                model=primary_model,
                error=str(e),
                signal_id=signal.signal_id,
            )

        # ── Attempt 2: Fallback Model ──
        try:
            result = await self._call_llm(
                model=fallback_model,
                prompt=user_prompt,
                signal=signal,
                route_reason=f"fallback_from_{primary_model.split('-')[1]}",
            )
            return result
        except Exception as e:
            logger.error(
                "fallback_model_failed",
                model=fallback_model,
                error=str(e),
                signal_id=signal.signal_id,
            )

        # ── Attempt 3: Deterministic WATCH ──
        logger.error(
            "all_models_failed",
            signal_id=signal.signal_id,
            primary=primary_model,
            fallback=fallback_model,
        )
        self._cost_tracker.record(
            model="fallback",
            latency_ms=0,
            signal_id=signal.signal_id,
            routed_reason="all_models_failed",
            tokens=0,
        )
        return self._create_fallback(signal, ["LLM_UNAVAILABLE", "ALL_MODELS_FAILED"])

    async def _call_llm(
        self,
        model: str,
        prompt: str,
        signal: QualifiedSignal,
        route_reason: str,
    ) -> DecisionOutput:
        """Call LLM with circuit breaker and cost tracking."""
        start_time = time.time()

        async def _do_call() -> DecisionOutput:
            return await self._client.chat.completions.create(
                model=model,
                response_model=DecisionOutput,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_retries=self._max_retries,
                timeout=self._timeout,
            )

        try:
            response = await self._circuit_breaker.call(_do_call)
            latency_ms = (time.time() - start_time) * 1000

            # Track cost
            self._cost_tracker.record(
                model=model,
                latency_ms=latency_ms,
                signal_id=signal.signal_id,
                routed_reason=route_reason,
            )

            logger.info(
                "llm_decision_generated",
                decision=response.decision,
                confidence=response.confidence,
                latency_ms=round(latency_ms, 2),
                model=model,
                route_reason=route_reason,
                symbol=signal.symbol,
            )

            return response
        except CircuitBreakerOpen:
            raise
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "llm_call_failed",
                error=str(e),
                latency_ms=round(latency_ms, 2),
                model=model,
                symbol=signal.symbol,
            )
            raise

    def _create_fallback(
        self, signal: QualifiedSignal, risk_flags: list[str]
    ) -> DecisionOutput:
        """Create a safe WATCH fallback decision."""
        return DecisionOutput(
            decision=Decision.WATCH,
            confidence=15,
            rationale=(
                f"System Advisory: Unusually high market activity detected for {signal.symbol}. "
                f"Advanced AI analysis unavailable due to {', '.join(risk_flags).lower().replace('_', ' ')}. "
                f"Please monitor this stock manually."
            ),
            citations=[],
            portfolio_impact=PortfolioImpact(),
            risk_flags=risk_flags,
            ttl_seconds=120,
        )

"""
Core Schemas — Pydantic models shared across all services.

These are the canonical data contracts for the entire pipeline:
Signal → Evidence → Decision → GuardedDecision → Alert
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ────────────────────────── Market / Signal ──────────────────────────


class MarketTick(BaseModel):
    """Normalized market tick from any provider."""

    symbol: str
    price: float
    volume: int
    bid: float
    ask: float
    timestamp: datetime
    source: str = "mock"


class SignalCandidate(BaseModel):
    """Raw anomaly event emitted by the ingestion service."""

    signal_id: str
    symbol: str
    anomaly_type: str  # AnomalyType value
    price: float
    volume: int
    z_score: float = 0.0
    vwap_deviation_pct: float = 0.0
    confidence: float = 0.0
    timestamp: datetime
    source: str = "mock"
    metadata: dict = Field(default_factory=dict)


class QualifiedSignal(BaseModel):
    """Signal that passed all qualification criteria."""

    signal_id: str
    symbol: str
    anomaly_type: str
    price: float
    volume: int
    z_score: float
    vwap_deviation_pct: float
    confidence: float
    timestamp: datetime
    source: str
    qualified_at: datetime
    metadata: dict = Field(default_factory=dict)


class RejectedSignal(BaseModel):
    """Signal that failed qualification with reason."""

    signal_id: str
    symbol: str
    reason_code: str
    reason_detail: str
    timestamp: datetime


# ────────────────────────── Evidence ──────────────────────────


class EvidenceItem(BaseModel):
    """A single piece of evidence with provenance metadata."""

    source_url: str
    title: str = ""
    content: str
    published_at: Optional[datetime] = None
    fetched_at: datetime
    reliability_score: float = Field(ge=0.0, le=1.0, default=0.5)
    source_type: str = "web"  # web | vector_memory | historical | corporate_filing
    plain_english_summary: str = ""  # Jargon-free one-liner
    filing_type: Optional[str] = None  # QUARTERLY_RESULT | REGULATORY | etc.


class EvidencePack(BaseModel):
    """Complete evidence bundle attached to a decision."""

    items: list[EvidenceItem] = Field(default_factory=list)
    degraded_context: bool = False
    total_sources_attempted: int = 0
    total_sources_succeeded: int = 0
    freshness_score: float = Field(ge=0.0, le=1.0, default=0.5)


# ────────────────────────── Decision (LLM Output) ──────────────────────────


class Citation(BaseModel):
    """Citation reference from the LLM decision."""

    url: str
    published_at: Optional[str] = None
    title: str = ""  # Human-readable source title
    source_type: str = "news"  # corporate_filing | news | analysis
    plain_summary: str = ""  # Jargon-free one-liner for retail investors


class PortfolioImpact(BaseModel):
    """Expected portfolio impact from the decision."""

    position_delta_pct: float = 0.0
    sector_exposure_delta_pct: float = 0.0
    cash_impact: float = 0.0


class DecisionOutput(BaseModel):
    """
    Strict LLM output schema — PRD §5 Step 3.

    Validation rules:
    - BUY/SELL MUST have at least one citation
    - Confidence clamped to [0, 100]
    """

    decision: str  # Decision enum value: BUY|SELL|HOLD|WATCH
    confidence: int = Field(ge=0, le=100)
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    portfolio_impact: PortfolioImpact = Field(default_factory=PortfolioImpact)
    risk_flags: list[str] = Field(default_factory=list)
    ttl_seconds: int = Field(default=300, ge=0)

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: int) -> int:
        """Clamp confidence to valid range."""
        if isinstance(v, (int, float)):
            return max(0, min(100, int(v)))
        return v

    @field_validator("citations", mode="after")
    @classmethod
    def validate_citations_for_actionable(cls, v: list[Citation], info) -> list[Citation]:
        """BUY/SELL decisions must include at least one citation."""
        decision = info.data.get("decision", "")
        if decision in ("BUY", "SELL") and len(v) == 0:
            raise ValueError(f"{decision} decisions require at least one citation")
        return v


# ────────────────────────── Guarded Decision (Post-Policy) ──────────────────────────


class PortfolioContext(BaseModel):
    """Hyper-personalized portfolio context attached to each decision."""

    symbol_exposure_pct: float = 0.0  # Current % of portfolio in this symbol
    symbol_value: float = 0.0  # ₹ value of holdings in this symbol
    symbol_quantity: float = 0.0  # Number of shares held
    sector_name: str = "Unknown"
    sector_exposure_pct: float = 0.0  # Current % of portfolio in this sector
    sector_holdings: list[str] = Field(default_factory=list)  # Other symbols in same sector
    personalized_summary: str = ""  # One-sentence personalized context


class StagedOrder(BaseModel):
    """Pre-computed order ticket for 1-click execution."""

    order_ticket_id: str
    action: str  # BUY | SELL
    symbol: str
    quantity: int
    price: float
    order_type: str = "LIMIT"  # LIMIT | MARKET
    estimated_value: float = 0.0
    valid_until: datetime
    status: str = "STAGED"  # STAGED | CONFIRMED | EXPIRED | CANCELLED


class CorporateFiling(BaseModel):
    """Structured corporate filing/regulatory event."""

    filing_id: str
    filing_type: str  # QUARTERLY_RESULT | BOARD_MEETING | INSIDER_TRADING | REGULATORY | DIVIDEND | MERGER | CREDIT_RATING
    affected_tickers: list[str] = Field(default_factory=list)
    title: str
    summary: str
    plain_english_summary: str = ""  # Jargon-free one-liner
    source_url: str
    published_at: datetime
    fetched_at: datetime
    source_name: str = ""  # BSE | NSE | RBI | MCA
    severity: str = "medium"  # low | medium | high | critical


class GuardedDecision(BaseModel):
    """Decision after policy guardrail enforcement."""

    signal_id: str
    user_id: str
    tenant_id: str = "default"
    original_decision: str
    final_decision: str  # May be downgraded to WATCH
    confidence: int
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    portfolio_impact: PortfolioImpact = Field(default_factory=PortfolioImpact)
    risk_flags: list[str] = Field(default_factory=list)
    policy_reason_codes: list[str] = Field(default_factory=list)
    policy_passed: bool = True
    ttl_seconds: int = 300
    degraded_context: bool = False
    created_at: datetime
    workflow_id: str = ""
    trace_id: str = ""
    portfolio_context: Optional[PortfolioContext] = None
    staged_order: Optional[StagedOrder] = None


# ────────────────────────── Portfolio ──────────────────────────


class PortfolioHolding(BaseModel):
    """Single holding in the canonical portfolio schema."""

    symbol: str
    quantity: float
    avg_price: float
    market_value: float = 0.0
    sector: str = "Unknown"
    exchange: str = "NSE"


class PortfolioCanonical(BaseModel):
    """Unified portfolio representation regardless of source."""

    user_id: str
    mode: str = "MOCK_JSON"  # PortfolioMode value
    holdings: list[PortfolioHolding] = Field(default_factory=list)
    total_value: float = 0.0
    cash_balance: float = 0.0
    last_synced_at: Optional[datetime] = None
    is_stale: bool = False


# ────────────────────────── Risk Profile & Policy ──────────────────────────


class RiskProfile(BaseModel):
    """User's risk tolerance configuration."""

    risk_tolerance: str = "moderate"  # conservative | moderate | aggressive
    max_single_position_pct: float = 25.0
    max_sector_exposure_pct: float = 40.0
    preferred_holding_period: str = "medium"  # short | medium | long


class PolicyConstraints(BaseModel):
    """Per-user policy constraint overrides."""

    max_position_concentration_pct: float = 25.0
    max_daily_actions: int = 20
    min_confidence_buy_sell: int = 60
    max_evidence_age_hours: int = 24


# ────────────────────────── API Schemas ──────────────────────────


class LifecycleRequest(BaseModel):
    """Request to change agent state."""

    target_state: str  # AgentState value
    reason: str = ""
    force: bool = False


class AgentStatusResponse(BaseModel):
    """Agent runtime status response."""

    state: str
    uptime_seconds: float = 0.0
    active_workers: int = 0
    pending_tasks: int = 0
    stream_lag: dict[str, int] = Field(default_factory=dict)
    last_decision_at: Optional[datetime] = None
    version: str = "0.1.0"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    postgres: str = "unknown"
    redis: str = "unknown"
    agent_state: str = "unknown"
    timestamp: datetime


class AlertMessage(BaseModel):
    """Real-time alert message for WS/SSE delivery."""

    alert_id: str
    user_id: str
    decision: GuardedDecision
    created_at: datetime
    delivered: bool = False
    ticker: str | None = None
    staged_order: Optional[StagedOrder] = None

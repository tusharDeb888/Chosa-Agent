"""
Demo Scenario API — Deterministic demo scenarios for reliable demonstrations.

Seeds stream events in a known sequence for predictable demo flows.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.observability import get_logger
from app.dependencies import get_redis

logger = get_logger("api.demo")
router = APIRouter(prefix="/demo")

# ── Demo Scenarios ──
SCENARIOS = {
    "earnings_shock": {
        "name": "Earnings Shock",
        "description": "TCS announces surprise buyback + strong Q4. INFY misses estimates.",
        "expected_outcomes": [
            "TCS: HOLD recommendation (buyback support)",
            "INFY: WATCH recommendation (miss + degraded context)",
            "Banking sector: BUY signal on sectoral rotation",
        ],
        "duration_seconds": 12,
        "events": [
            {
                "ticker": "TCS", "decision": "HOLD", "confidence": 72,
                "anomaly": "CORPORATE_FILING",
                "rationale": "TCS board approves ₹18,000 Cr share buyback at ₹4,150 — a 10% premium to current price. This signals strong management confidence. Your ₹7.6L in TCS (12% of portfolio) benefits from buyback premium. Hold and tender shares if price reaches buyback threshold.",
                "risk_flags": [],
                "portfolio_impact": {"position_delta_pct": 0, "sector_exposure_delta_pct": 0.5, "cash_impact": 0},
                "citations": [
                    {"url": "https://www.bseindia.com/corporates/annDet.aspx?scrip=532540", "published_at": "2026-03-28T07:00:00Z", "title": "TCS Board Meeting — Share Buyback Approved ₹18,000 Cr", "source_type": "corporate_filing", "plain_summary": "TCS board approved a buyback of up to ₹18,000 crore at ₹4,150 per share, representing a 10% premium to market price."},
                ],
                "ttl": 600,
            },
            {
                "ticker": "INFY", "decision": "WATCH", "confidence": 28,
                "anomaly": "VOLUME_SPIKE",
                "rationale": "⚠️ System Advisory: INFY reports Q4 revenue miss of 2.3%. Our AI analysis engine encountered partial data from one evidence source. Your ₹4.1L in INFY (6.5% of portfolio) is not at immediate risk, but monitor for further guidance revisions.",
                "risk_flags": ["LLM_UNCERTAINTY", "DEGRADED_CONTEXT"],
                "portfolio_impact": {"position_delta_pct": 0, "sector_exposure_delta_pct": 0, "cash_impact": 0},
                "citations": [],
                "ttl": 120,
            },
            {
                "ticker": "ICICIBANK", "decision": "BUY", "confidence": 81,
                "anomaly": "VOLUME_SPIKE",
                "rationale": "Sectoral rotation signal: IT sector weakness is driving capital into banking stocks. ICICIBANK volume is 3.8x above 5-min EMA with consistent bid-side pressure. Your banking exposure (28.5%) is within the 40% sector limit. Consider adding to position.",
                "risk_flags": [],
                "portfolio_impact": {"position_delta_pct": 4.5, "sector_exposure_delta_pct": 3.2, "cash_impact": -55000},
                "citations": [
                    {"url": "https://economictimes.com/banking-sector-flows", "published_at": "2026-03-28T10:30:00Z", "title": "Banking Stocks See Heavy Inflows as IT Sector Rotates Out", "source_type": "news", "plain_summary": "Institutional investors are moving money from IT stocks into banking, with ICICI Bank and HDFC Bank seeing the highest net inflows."},
                ],
                "ttl": 300,
            },
        ],
    },
    "volume_spike": {
        "name": "Volume Spike",
        "description": "ICICIBANK sees 4x volume with institutional buying. HDFCBANK under RBI pressure.",
        "expected_outcomes": [
            "ICICIBANK: BUY with high confidence (volume confirmation)",
            "HDFCBANK: SELL recommendation (concentration + regulatory risk)",
            "Portfolio risk: Sector concentration warning",
        ],
        "duration_seconds": 10,
        "events": [
            {
                "ticker": "ICICIBANK", "decision": "BUY", "confidence": 85,
                "anomaly": "VOLUME_SPIKE",
                "rationale": "Volume spike 4.2x above EMA confirmed by institutional order flow analysis. ICICI Bank Q4 PAT up 22% — strong fundamental support. Your ₹5.2L position (8.2%) has room to grow within risk limits.",
                "risk_flags": [],
                "portfolio_impact": {"position_delta_pct": 5.1, "sector_exposure_delta_pct": 3.8, "cash_impact": -62000},
                "citations": [
                    {"url": "https://economictimes.com/icici-q4-results", "published_at": "2026-03-28T10:00:00Z", "title": "ICICI Bank Q4: Net Profit Surges 22%, Beats Estimates", "source_type": "news", "plain_summary": "ICICI Bank reported a 22% jump in net profit to ₹11,672 Cr, beating analyst expectations by 8%."},
                ],
                "ttl": 300,
                "staged_order": {
                    "order_ticket_id": "demo-scenario-001", "action": "BUY", "symbol": "ICICIBANK",
                    "quantity": 55, "price": 1058.00, "order_type": "LIMIT",
                    "estimated_value": 58190, "status": "STAGED",
                },
            },
            {
                "ticker": "HDFCBANK", "decision": "SELL", "confidence": 74,
                "anomaly": "SPREAD_ANOMALY",
                "rationale": "⚠️ Your ₹18.5L in HDFCBANK (28%) EXCEEDS your 25% max concentration limit. RBI's new risk weight norms will compress NII margins by ~40bps. Spread anomaly shows 2.8x ask-side pressure. Recommend trimming position by 10% to bring within limits.",
                "risk_flags": ["MAX_CONCENTRATION_EXCEEDED"],
                "portfolio_impact": {"position_delta_pct": -8.5, "sector_exposure_delta_pct": -6.2, "cash_impact": 185000},
                "citations": [
                    {"url": "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12540", "published_at": "2026-03-28T08:00:00Z", "title": "RBI Circular: Revised Risk Weights on Consumer Lending", "source_type": "corporate_filing", "plain_summary": "RBI mandates higher risk weights on personal loans, impacting bank capital requirements."},
                ],
                "ttl": 240,
                "staged_order": {
                    "order_ticket_id": "demo-scenario-002", "action": "SELL", "symbol": "HDFCBANK",
                    "quantity": 112, "price": 1647.50, "order_type": "LIMIT",
                    "estimated_value": 184520, "status": "STAGED",
                },
            },
        ],
    },
    "market_closed_filing": {
        "name": "Market Closed + Filing Alert",
        "description": "After-hours corporate filing triggers advisory during market closed.",
        "expected_outcomes": [
            "RELIANCE: WATCH (promoter stake sale filing)",
            "News Radar active 24/7 monitoring",
            "Advisory-only mode (no actionable trades until market opens)",
        ],
        "duration_seconds": 8,
        "events": [
            {
                "ticker": "RELIANCE", "decision": "WATCH", "confidence": 45,
                "anomaly": "CORPORATE_FILING",
                "rationale": "After-hours filing: Reliance promoter entity sold ₹957 Cr worth of shares (0.12% stake reduction). While this is a small fraction, it could signal upcoming restructuring. Your ₹9.6L in RELIANCE (15.1%) — your largest holding — deserves monitoring. No action needed until market opens.",
                "risk_flags": ["MARKET_CLOSED"],
                "portfolio_impact": {"position_delta_pct": 0, "sector_exposure_delta_pct": 0, "cash_impact": 0},
                "citations": [
                    {"url": "https://www.nseindia.com/companies-listing/corporate-filings-insider-trading", "published_at": "2026-03-28T18:30:00Z", "title": "Reliance — Promoter Stake Sale (SAST Filing)", "source_type": "corporate_filing", "plain_summary": "A Reliance promoter entity sold ₹957 Cr worth of shares, reducing stake to 50.29%. Filed after market hours."},
                ],
                "ttl": 43200,
            },
            {
                "ticker": "SBIN", "decision": "HOLD", "confidence": 58,
                "anomaly": "MOMENTUM_BREAK",
                "rationale": "SBI announced ₹5,000 Cr QIP (Qualified Institutional Placement) after market hours. This will dilute existing shareholders by ~1.2% but strengthens the bank's capital position. Your position in SBIN is small — hold and monitor the placement pricing.",
                "risk_flags": [],
                "portfolio_impact": {"position_delta_pct": -1.2, "sector_exposure_delta_pct": -0.3, "cash_impact": 0},
                "citations": [
                    {"url": "https://www.bseindia.com/corporates/annDet.aspx?scrip=500112", "published_at": "2026-03-28T19:00:00Z", "title": "SBI Board Approves ₹5,000 Cr QIP", "source_type": "corporate_filing", "plain_summary": "SBI approved raising ₹5,000 crore through QIP to strengthen its capital base, pending shareholder approval."},
                ],
                "ttl": 28800,
            },
        ],
    },
}


class DemoRunResponse(BaseModel):
    scenario: str
    name: str
    description: str
    expected_outcomes: list[str]
    event_count: int
    duration_seconds: int
    status: str


@router.get("/scenarios")
async def list_scenarios():
    """List all available demo scenarios."""
    return {
        "scenarios": [
            {
                "id": k,
                "name": v["name"],
                "description": v["description"],
                "expected_outcomes": v["expected_outcomes"],
                "event_count": len(v["events"]),
                "duration_seconds": v["duration_seconds"],
            }
            for k, v in SCENARIOS.items()
        ]
    }


@router.post("/run")
async def run_demo_scenario(
    scenario: str = Query(default="earnings_shock", description="Scenario ID"),
):
    """
    Run a demo scenario — seeds deterministic alert events.

    Returns immediately with scenario metadata.
    Events are published to the alerts stream for WS delivery.
    """
    if scenario not in SCENARIOS:
        return {
            "status": "error",
            "message": f"Unknown scenario: {scenario}. Available: {list(SCENARIOS.keys())}",
        }

    sc = SCENARIOS[scenario]

    # Try to publish events to Redis stream for WS delivery
    try:
        redis_client = await get_redis()
        now = datetime.now(timezone.utc)

        for i, event in enumerate(sc["events"]):
            alert_id = f"demo-{scenario}-{uuid.uuid4().hex[:8]}"
            created_at = (now + __import__("datetime").timedelta(seconds=i * 2)).isoformat()

            staged_order = event.get("staged_order")
            if staged_order:
                staged_order["order_ticket_id"] = f"{staged_order['order_ticket_id']}-{uuid.uuid4().hex[:4]}"
                staged_order["valid_until"] = (now + __import__("datetime").timedelta(seconds=event["ttl"])).isoformat()

            alert_payload = {
                "alert_id": alert_id,
                "user_id": "demo",
                "ticker": event["ticker"],
                "created_at": created_at,
                "staged_order": staged_order,
                "decision": {
                    "signal_id": f"{event['ticker']}-{event['anomaly']}-{uuid.uuid4().hex[:6]}",
                    "user_id": "demo",
                    "tenant_id": "default",
                    "original_decision": event["decision"],
                    "final_decision": event["decision"],
                    "confidence": event["confidence"],
                    "rationale": event["rationale"],
                    "citations": event.get("citations", []),
                    "portfolio_impact": event["portfolio_impact"],
                    "risk_flags": event["risk_flags"],
                    "policy_reason_codes": [],
                    "policy_passed": "MAX_CONCENTRATION_EXCEEDED" not in event["risk_flags"],
                    "ttl_seconds": event["ttl"],
                    "degraded_context": "DEGRADED_CONTEXT" in event["risk_flags"],
                    "created_at": created_at,
                    "workflow_id": f"demo-wf-{scenario}-{i}",
                    "trace_id": f"demo-trace-{scenario}-{i}",
                    "staged_order": staged_order,
                },
            }

            # Publish to notification stream
            await redis_client.xadd(
                "alpha-hunter:alerts.user_feed",
                {"data": json.dumps(alert_payload, default=str)},
            )

            logger.info(
                "demo_event_published",
                scenario=scenario,
                ticker=event["ticker"],
                decision=event["decision"],
            )

    except Exception as e:
        logger.warning("demo_redis_publish_failed", error=str(e))
        # Events will still be returned for client-side playback

    return {
        "status": "started",
        "scenario": scenario,
        "name": sc["name"],
        "description": sc["description"],
        "expected_outcomes": sc["expected_outcomes"],
        "event_count": len(sc["events"]),
        "duration_seconds": sc["duration_seconds"],
        "events": sc["events"],
    }

"""
Explainability API — Full explainability payload for alerts.

Computes trust scores server-side and returns enriched evidence timeline.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Path, Query

from app.core.observability import get_logger

logger = get_logger("api.explain")
router = APIRouter(prefix="/explain")


def compute_trust_score(
    confidence: float,
    created_at: str | None,
    policy_passed: bool,
    citations_count: int,
    degraded_context: bool,
    risk_flags: list[str] | None = None,
) -> dict:
    """
    Compute trust score server-side.

    Formula: confidence*0.4 + freshness*0.3 + policy*0.2 + sources*0.1 - degraded_penalty
    """
    # Normalize confidence (0-1)
    confidence_norm = min(max(confidence, 0), 100) / 100

    # Freshness (decays over 24h)
    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            hours_ago = (datetime.now(timezone.utc) - created).total_seconds() / 3600
            freshness_norm = max(0, 1 - hours_ago / 24)
        except Exception:
            freshness_norm = 0.5
    else:
        freshness_norm = 0.5

    # Policy pass
    policy_score = 1.0 if policy_passed else 0.0

    # Source reliability
    source_reliability = min(citations_count / 3, 1.0) if citations_count > 0 else 0.2

    # Degraded penalty
    degraded_penalty = 0.3 if degraded_context else 0

    # Risk flag penalty
    risk_penalty = 0
    if risk_flags:
        if "LLM_UNAVAILABLE" in risk_flags:
            risk_penalty += 0.2
        if "EVIDENCE_SPARSE" in risk_flags:
            risk_penalty += 0.1

    raw = (
        confidence_norm * 0.4
        + freshness_norm * 0.3
        + policy_score * 0.2
        + source_reliability * 0.1
        - degraded_penalty
        - risk_penalty
    )

    score = round(max(0, min(1, raw)) * 100)

    if score >= 70:
        label = "Safe Advisory"
    elif score >= 40:
        label = "Review Needed"
    else:
        label = "High Risk"

    return {
        "score": score,
        "label": label,
        "factors": {
            "confidence_normalized": round(confidence_norm, 3),
            "freshness_normalized": round(freshness_norm, 3),
            "policy_pass": policy_passed,
            "source_reliability": round(source_reliability, 3),
            "degraded_context": degraded_context,
            "risk_flags_count": len(risk_flags) if risk_flags else 0,
        },
    }


@router.get("/{explainability_id}")
async def get_explainability(
    explainability_id: str = Path(..., description="The explainability ID from an alert"),
):
    """
    Full explainability payload for a given alert/signal.

    In production, this would fetch from the decision log database.
    For now, returns a structured demo response.
    """
    # In production: query agent_execution_logs table by explainability_id
    # For demo, return structured response

    return {
        "id": explainability_id,
        "status": "available",
        "message": "Explainability data is embedded in the alert payload. Use the ExplainDrawer component for full details.",
        "trust_score_endpoint": "POST /api/v1/explain/trust-score",
    }


@router.post("/trust-score")
async def compute_trust_score_api(body: dict):
    """
    Compute trust score for an alert decision.

    Request body:
    {
        "confidence": 78,
        "created_at": "2026-03-28T10:00:00Z",
        "policy_passed": true,
        "citations_count": 2,
        "degraded_context": false,
        "risk_flags": ["SECTOR_CONCENTRATION"]
    }
    """
    result = compute_trust_score(
        confidence=body.get("confidence", 0),
        created_at=body.get("created_at"),
        policy_passed=body.get("policy_passed", True),
        citations_count=body.get("citations_count", 0),
        degraded_context=body.get("degraded_context", False),
        risk_flags=body.get("risk_flags", []),
    )

    return result

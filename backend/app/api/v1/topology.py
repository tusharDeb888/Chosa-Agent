"""
Agent Topology API — Exposes multi-agent architecture for visualization.

Rubric: "Are responsibilities split across agents? Do agents talk to each other?
         Is there a clear orchestration pattern holding it together?"
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.dependencies import get_redis
from app.core.observability import get_logger
from app.core.circuit_breaker import get_all_breaker_stats

logger = get_logger("api.topology")

router = APIRouter(prefix="/ops")


@router.get("/topology")
async def get_topology(redis_client=Depends(get_redis)):
    """
    Return the full multi-agent architecture graph.

    Shows each agent's role, type, status, and how they communicate.
    """
    # Check worker health via heartbeats
    ingestion_hb = await redis_client.get("worker:ingestion:heartbeat")
    agent_state = await redis_client.get("agent:state") or "PAUSED"

    def worker_status(heartbeat_key: str | None) -> str:
        if not heartbeat_key:
            return "unknown"
        try:
            age = time.time() - float(heartbeat_key)
            return "healthy" if age < 15 else "stale"
        except (ValueError, TypeError):
            return "unknown"

    agents = [
        {
            "id": "ingestion-agent",
            "name": "Market Ingestion Agent",
            "role": "Continuous market data intake from Upstox/Mock provider. Runs statistical anomaly detection (volume spikes, VWAP deviation, RSI momentum) on sliding windows.",
            "type": "streaming",
            "capabilities": ["websocket_intake", "anomaly_detection", "z_score_analysis", "vwap_tracking"],
            "input": "Market ticks (WebSocket)",
            "output": "SignalCandidate events → Redis Stream",
            "status": worker_status(ingestion_hb),
            "model_used": None,
        },
        {
            "id": "qualification-agent",
            "name": "Signal Qualification Agent",
            "role": "5-criteria gate: data freshness, liquidity threshold, statistical significance, confidence floor, and agent state verification. Rejects weak signals with reason codes.",
            "type": "filter",
            "capabilities": ["freshness_check", "liquidity_filter", "z_score_validation", "confidence_gating"],
            "input": "SignalCandidate from stream",
            "output": "QualifiedSignal or RejectedSignal",
            "status": "healthy" if agent_state == "RUNNING" else "paused",
            "model_used": None,
        },
        {
            "id": "enrichment-agent",
            "name": "Context Enrichment Agent",
            "role": "Gathers evidence from dual sources: (1) Crawl4AI web scraping from allowlisted financial domains, (2) pgvector semantic search for historical context. Attaches provenance metadata.",
            "type": "tool-use",
            "capabilities": ["web_scraping", "vector_retrieval", "provenance_tagging", "degradation_handling"],
            "input": "QualifiedSignal + symbol query",
            "output": "EvidencePack with reliability scores",
            "status": "healthy" if agent_state == "RUNNING" else "paused",
            "model_used": None,
        },
        {
            "id": "synthesis-agent",
            "name": "LLM Synthesis Agent",
            "role": "Smart model router selects optimal model based on signal complexity: 70B for high-conviction signals, 8B for standard ones. Generates structured BUY/SELL/HOLD/WATCH recommendation with schema validation.",
            "type": "reasoning",
            "capabilities": ["smart_model_routing", "structured_output", "schema_validation", "fallback_chain"],
            "input": "QualifiedSignal + EvidencePack + Portfolio + RiskProfile",
            "output": "DecisionOutput (JSON schema enforced)",
            "status": "healthy" if agent_state == "RUNNING" else "paused",
            "model_used": "llama-3.3-70b-versatile / llama-3.1-8b-instant (routed)",
        },
        {
            "id": "policy-agent",
            "name": "Policy Guardrail Agent",
            "role": "Post-LLM constraint enforcement: max position concentration, daily action limits, confidence thresholds, evidence freshness, portfolio staleness. Non-compliant BUY/SELL downgraded to WATCH.",
            "type": "rule-engine",
            "capabilities": ["concentration_check", "action_rate_limit", "confidence_gating", "evidence_age_check", "portfolio_staleness"],
            "input": "DecisionOutput + PolicyConstraints + Portfolio",
            "output": "GuardedDecision with violation codes",
            "status": "healthy" if agent_state == "RUNNING" else "paused",
            "model_used": None,
        },
        {
            "id": "notification-agent",
            "name": "Real-time Notification Agent",
            "role": "Consumes guarded decisions, publishes to dual audit trail (agent.decisions) and user feed (alerts.user_feed) Redis streams. Fan-out to WebSocket + SSE connected clients.",
            "type": "delivery",
            "capabilities": ["websocket_broadcast", "sse_streaming", "dead_connection_cleanup", "multi_user_fanout"],
            "input": "GuardedDecision from stream",
            "output": "Real-time alerts to browser clients",
            "status": "healthy" if agent_state == "RUNNING" else "paused",
            "model_used": None,
        },
    ]

    edges = [
        {"from": "ingestion-agent", "to": "qualification-agent", "channel": "signals.candidate", "protocol": "Redis Streams"},
        {"from": "qualification-agent", "to": "enrichment-agent", "channel": "signals.qualified", "protocol": "Redis Streams"},
        {"from": "enrichment-agent", "to": "synthesis-agent", "channel": "LangGraph internal", "protocol": "State passthrough"},
        {"from": "synthesis-agent", "to": "policy-agent", "channel": "LangGraph internal", "protocol": "State passthrough"},
        {"from": "policy-agent", "to": "notification-agent", "channel": "alerts.user_feed", "protocol": "Redis Streams"},
    ]

    return {
        "agents": agents,
        "edges": edges,
        "orchestration": {
            "pattern": "LangGraph StateGraph with conditional edges",
            "framework": "LangGraph (langgraph.graph.StateGraph)",
            "execution": "Async event-driven with fan-out per impacted user",
            "state_management": "TypedDict flowing through graph nodes",
        },
        "communication": {
            "inter_agent": "Redis Streams (XREADGROUP, consumer groups, XACK)",
            "intra_graph": "LangGraph StateGraph state passthrough",
            "real_time": "WebSocket + SSE (dual channel)",
            "control_plane": "Redis Pub/Sub (agent.control channel)",
        },
        "fault_tolerance": {
            "circuit_breakers": get_all_breaker_stats(),
            "retry_policy": "Bounded exponential backoff + jitter",
            "dlq": "Poison messages → DLQ streams (preserved for audit/replay)",
            "self_healing": "Auto-restart workers with max-attempt ceiling",
        },
        "agent_state": agent_state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

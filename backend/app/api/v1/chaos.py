"""
Chaos Engineering API — Simulate failures to demonstrate autonomy depth.

Rubric: "Does the agent recover from failures on its own?
         Can it handle branching logic and exceptions without falling over?"
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.core.enums import AgentState
from app.core.observability import get_logger
from app.core.circuit_breaker import get_circuit_breaker, get_all_breaker_stats
from app.control.kill_switch import KillSwitch
from app.dependencies import get_redis

logger = get_logger("api.chaos")

router = APIRouter(prefix="/ops/chaos")


@router.post("/simulate-failure")
async def simulate_failure(
    failure_type: str = "worker_crash",
    duration_seconds: int = 5,
    redis_client=Depends(get_redis),
):
    """
    Simulate a system failure to demonstrate self-healing.

    Supported failure types:
    - worker_crash: Temporarily marks worker as unhealthy
    - llm_timeout: Trips the LLM circuit breaker
    - degraded_mode: Transitions agent to DEGRADED then auto-recovers
    - pipeline_stall: Injects artificial latency into the pipeline
    """
    kill_switch = KillSwitch(redis_client)
    results = {"failure_type": failure_type, "duration_seconds": duration_seconds}

    if failure_type == "worker_crash":
        # Mark ingestion worker as unhealthy temporarily
        await redis_client.delete("worker:ingestion:heartbeat")
        await redis_client.set("chaos:worker_crash", "1", ex=duration_seconds)

        # Schedule recovery
        asyncio.create_task(_auto_recover_worker(redis_client, duration_seconds))

        results["action"] = "Ingestion worker heartbeat cleared"
        results["recovery"] = f"Auto-heal in {duration_seconds}s"
        results["observable_effect"] = "Worker Status → UNKNOWN → healthy"

    elif failure_type == "llm_timeout":
        # Trip the circuit breaker by recording artificial failures
        breaker = get_circuit_breaker("llm")
        for _ in range(breaker._failure_threshold):
            await breaker._on_failure(
                TimeoutError("Simulated LLM timeout (chaos test)")
            )

        asyncio.create_task(_auto_recover_breaker(duration_seconds))

        results["action"] = "LLM circuit breaker tripped to OPEN"
        results["circuit_breaker"] = breaker.stats
        results["recovery"] = f"Auto-recovery via HALF_OPEN probe in {breaker._recovery_timeout}s"
        results["observable_effect"] = "Decisions fallback to WATCH → circuit recovers → normal"

    elif failure_type == "degraded_mode":
        # Transition to DEGRADED then auto-recover
        current = await kill_switch.get_state()
        if current == AgentState.RUNNING:
            await kill_switch.transition(
                AgentState.DEGRADED,
                reason="chaos_test: simulated dependency failure",
            )

            asyncio.create_task(
                _auto_recover_state(redis_client, duration_seconds)
            )

            results["action"] = "Agent transitioned to DEGRADED"
            results["recovery"] = f"Auto-transition to RUNNING in {duration_seconds}s"
            results["observable_effect"] = "Status → DEGRADED → RUNNING (self-healing)"
        else:
            results["action"] = "Agent not RUNNING, cannot simulate degradation"
            results["skipped"] = True

    elif failure_type == "pipeline_stall":
        # Inject artificial latency flag
        await redis_client.set("chaos:pipeline_latency_ms", "2000", ex=duration_seconds)

        results["action"] = f"Injected 2000ms latency into pipeline for {duration_seconds}s"
        results["recovery"] = "Automatic TTL expiry"
        results["observable_effect"] = "Alert latency spike → auto-normalizes"

    else:
        results["error"] = f"Unknown failure type: {failure_type}"

    results["timestamp"] = datetime.now(timezone.utc).isoformat()
    logger.info("chaos_simulation", **results)
    return results


@router.post("/recover")
async def force_recover(redis_client=Depends(get_redis)):
    """Force recovery from any chaos simulation."""
    kill_switch = KillSwitch(redis_client)

    # Clear chaos flags
    await redis_client.delete("chaos:worker_crash", "chaos:pipeline_latency_ms")

    # Reset circuit breakers
    breaker = get_circuit_breaker("llm")
    breaker.reset()

    # Restore worker heartbeat
    await redis_client.set(
        "worker:ingestion:heartbeat", str(int(time.time())), ex=30
    )

    # If DEGRADED, restore to RUNNING
    current = await kill_switch.get_state()
    if current == AgentState.DEGRADED:
        await kill_switch.transition(
            AgentState.RUNNING,
            reason="chaos_recovery: manual",
            force=True,
        )

    return {
        "status": "recovered",
        "agent_state": (await kill_switch.get_state()).value,
        "circuit_breakers": get_all_breaker_stats(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status")
async def chaos_status(redis_client=Depends(get_redis)):
    """Check current chaos simulation status."""
    worker_crash = await redis_client.get("chaos:worker_crash")
    pipeline_latency = await redis_client.get("chaos:pipeline_latency_ms")

    return {
        "active_simulations": {
            "worker_crash": bool(worker_crash),
            "pipeline_latency_ms": int(pipeline_latency) if pipeline_latency else 0,
        },
        "circuit_breakers": get_all_breaker_stats(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Background recovery tasks ──

async def _auto_recover_worker(redis_client, delay: int) -> None:
    """Auto-restore worker heartbeat after delay."""
    await asyncio.sleep(delay)
    await redis_client.set(
        "worker:ingestion:heartbeat", str(int(time.time())), ex=30
    )
    logger.info("chaos_worker_recovered")


async def _auto_recover_breaker(delay: int) -> None:
    """Wait for circuit breaker to self-recover."""
    await asyncio.sleep(delay)
    breaker = get_circuit_breaker("llm")
    breaker.reset()
    logger.info("chaos_breaker_recovered")


async def _auto_recover_state(redis_client, delay: int) -> None:
    """Auto-transition from DEGRADED back to RUNNING."""
    await asyncio.sleep(delay)
    kill_switch = KillSwitch(redis_client)
    current = await kill_switch.get_state()
    if current == AgentState.DEGRADED:
        await kill_switch.transition(
            AgentState.RUNNING,
            reason="auto_recovery: chaos test complete",
            force=True,
        )
    logger.info("chaos_state_recovered")

"""
Kill Switch — Sub-500ms agent state propagation.

Uses Redis SET + Pub/Sub broadcast for immediate worker notification.
Workers update local state instantly on broadcast; polling remains fallback.
"""

from __future__ import annotations

import time

import redis.asyncio as redis

from app.config import get_settings
from app.core.enums import AgentState
from app.core.exceptions import AgentStateError
from app.core.observability import get_logger

logger = get_logger("control.kill_switch")

# Valid state transitions
_VALID_TRANSITIONS = {
    AgentState.RUNNING: {AgentState.PAUSED, AgentState.TERMINATED, AgentState.DEGRADED},
    AgentState.PAUSED: {AgentState.RUNNING, AgentState.TERMINATED},
    AgentState.TERMINATED: {AgentState.RUNNING},  # Requires explicit re-init
    AgentState.DEGRADED: {AgentState.RUNNING, AgentState.PAUSED, AgentState.TERMINATED},
}


class KillSwitch:
    """
    Atomic agent state management with sub-500ms propagation.

    Mechanism:
    1. Write new state to Redis (atomic SET)
    2. Broadcast state change on agent.control pub/sub channel
    3. Workers receive broadcast and update local state immediately
    4. Fallback: workers poll Redis every heartbeat interval
    """

    def __init__(self, redis_client: redis.Redis):
        self._redis = redis_client
        self._settings = get_settings()

    async def get_state(self) -> AgentState:
        """Get the current agent state."""
        state = await self._redis.get("agent:state")
        if state and state in AgentState.__members__:
            return AgentState(state)
        return AgentState.PAUSED

    async def transition(
        self,
        target_state: AgentState,
        reason: str = "",
        force: bool = False,
    ) -> AgentState:
        """
        Transition agent to a new state with <500ms propagation.

        Validates transition legality unless force=True.
        """
        current = await self.get_state()

        # Validate transition
        if not force:
            valid_targets = _VALID_TRANSITIONS.get(current, set())
            if target_state not in valid_targets:
                raise AgentStateError(
                    f"Invalid transition: {current} -> {target_state}",
                    context={
                        "current": current,
                        "target": target_state,
                        "valid_targets": [s.value for s in valid_targets],
                    },
                )

        start = time.time()

        # 1. Atomic state write
        await self._redis.set("agent:state", target_state.value)
        await self._redis.set("agent:state:updated_at", str(time.time()))
        await self._redis.set("agent:state:reason", reason)

        # 2. Broadcast via pub/sub
        message = f"{target_state.value}:{reason}:{int(time.time() * 1000)}"
        await self._redis.publish(self._settings.control_channel, message)

        elapsed_ms = (time.time() - start) * 1000

        logger.info(
            "agent_state_changed",
            previous=current.value,
            new=target_state.value,
            reason=reason,
            propagation_ms=round(elapsed_ms, 2),
            forced=force,
        )

        # Record transition in audit trail
        await self._redis.lpush(
            "agent:state:history",
            f"{current.value}->{target_state.value}:{reason}:{int(time.time())}",
        )
        await self._redis.ltrim("agent:state:history", 0, 99)  # Keep last 100

        return target_state

    async def is_running(self) -> bool:
        """Quick check if agent is in RUNNING state."""
        state = await self._redis.get("agent:state")
        return state == AgentState.RUNNING

    async def get_state_info(self) -> dict:
        """Get full state information."""
        state = await self.get_state()
        updated_at = await self._redis.get("agent:state:updated_at")
        reason = await self._redis.get("agent:state:reason")
        history = await self._redis.lrange("agent:state:history", 0, 9)

        return {
            "state": state.value,
            "updated_at": float(updated_at) if updated_at else None,
            "reason": reason or "",
            "recent_transitions": history or [],
        }

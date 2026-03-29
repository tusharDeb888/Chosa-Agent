"""
FastAPI Dependencies — Dependency injection for the application.
"""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncGenerator

import redis.asyncio as redis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.engine import get_db_session

# ────────────────────────── Redis ──────────────────────────

_redis_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get the shared Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        settings = get_settings()
        _redis_pool = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool on shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


# ────────────────────────── Dependencies ──────────────────────────


async def get_db(session: AsyncSession = Depends(get_db_session)) -> AsyncSession:
    """FastAPI-compatible database session dependency."""
    return session


def get_config() -> Settings:
    """FastAPI-compatible settings dependency."""
    return get_settings()

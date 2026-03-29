"""
Portfolio API Routes — Mock import and sync endpoints.
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_db_session
from app.db.repositories import UserRepository
from app.dependencies import get_redis
from app.portfolio.service import PortfolioService

router = APIRouter(prefix="/portfolio")


class MockPortfolioRequest(BaseModel):
    """Request body for mock portfolio import."""
    user_email: str = "demo@alphahunter.ai"
    holdings: list[dict] = []
    cash_balance: float = 100000.0


class PortfolioSymbolsRequest(BaseModel):
    """Request body for updating watched symbols."""
    symbols: list[str]


@router.post("/symbols", response_model=dict)
async def update_watch_symbols(
    request: PortfolioSymbolsRequest,
    redis_client=Depends(get_redis),
):
    """
    Update the list of portfolio symbols the ingestion worker should watch.

    Called by the frontend when the user's portfolio changes or on agent Start.
    Symbols are stored in Redis under 'portfolio:watch_symbols' and picked up
    by the ingestion worker on its next cycle.
    """
    clean_symbols = [s.strip().upper() for s in request.symbols if s.strip()]
    if not clean_symbols:
        raise HTTPException(status_code=400, detail="No valid symbols provided")

    await redis_client.set(
        "portfolio:watch_symbols",
        json.dumps(clean_symbols),
    )
    return {
        "status": "ok",
        "symbols": clean_symbols,
        "message": f"Ingestion worker will now watch {len(clean_symbols)} symbols",
    }


@router.post("/mock", response_model=dict)
async def import_mock_portfolio(
    request: MockPortfolioRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Import a mock portfolio from JSON."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(request.user_email)

    if not user:
        # Create demo user if not exists
        user = await user_repo.create(
            email=request.user_email,
            name="Demo User",
            agent_state="PAUSED",
        )
        await session.commit()

    portfolio_service = PortfolioService(session)

    try:
        portfolio = await portfolio_service.import_mock(
            user_id=user.id,
            holdings_data=request.holdings,
            cash_balance=request.cash_balance,
        )
        return {
            "status": "ok",
            "user_id": str(user.id),
            "total_value": portfolio.total_value,
            "positions": len(portfolio.holdings),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/upstox", response_model=dict)
async def sync_upstox_portfolio():
    """Sync portfolio from Upstox (stub in Phase 1)."""
    return {
        "status": "stub",
        "message": "Upstox portfolio sync is not yet implemented. Use mock mode.",
    }


@router.get("/{user_id}", response_model=dict)
async def get_portfolio(
    user_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get portfolio for a user."""
    portfolio_service = PortfolioService(session)
    portfolio = await portfolio_service.get_portfolio(uuid.UUID(user_id))

    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    return portfolio.model_dump(mode="json")

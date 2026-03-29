"""
Portfolio Service — Mock and Live portfolio management.

CRITICAL: Portfolio write MUST update both `portfolios` and `portfolio_positions`
in ONE transaction. Rollback all on failure.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PortfolioMode
from app.core.schemas import PortfolioCanonical, PortfolioHolding
from app.core.observability import get_logger, traced
from app.db.repositories import PortfolioRepository, PositionRepository

logger = get_logger("portfolio.service")


class PortfolioService:
    """
    Portfolio operations — modes: MOCK_JSON and UPSTOX_LIVE.

    Enforces atomic consistency: portfolios + portfolio_positions
    updated in one transaction.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._portfolio_repo = PortfolioRepository(session)
        self._position_repo = PositionRepository(session)

    @traced("portfolio.import_mock")
    async def import_mock(
        self,
        user_id: uuid.UUID,
        holdings_data: list[dict[str, Any]],
        cash_balance: float = 100000.0,
        tenant_id: str = "default",
    ) -> PortfolioCanonical:
        """
        Import a mock portfolio from JSON data.

        Atomically updates both portfolios and portfolio_positions tables.
        """
        # Calculate totals
        total_value = cash_balance
        positions = []
        holdings_items = []

        for item in holdings_data:
            qty = float(item.get("quantity", 0))
            avg_price = float(item.get("avg_price", 0))
            market_value = qty * avg_price
            total_value += market_value

            positions.append({
                "symbol": item["symbol"],
                "quantity": qty,
                "avg_price": avg_price,
                "market_value": market_value,
                "sector": item.get("sector", "Unknown"),
                "exchange": item.get("exchange", "NSE"),
            })

            holdings_items.append({
                "symbol": item["symbol"],
                "quantity": qty,
                "avg_price": avg_price,
                "market_value": market_value,
                "sector": item.get("sector", "Unknown"),
                "exchange": item.get("exchange", "NSE"),
            })

        # ── ATOMIC TRANSACTION ──
        try:
            # Update portfolio
            portfolio = await self._portfolio_repo.upsert(
                user_id=user_id,
                tenant_id=tenant_id,
                mode=PortfolioMode.MOCK_JSON,
                holdings={"items": holdings_items},
                total_value=total_value,
                cash_balance=cash_balance,
                last_synced_at=datetime.now(timezone.utc),
                is_stale=False,
            )

            # Sync positions (atomic — within same session)
            await self._position_repo.sync_positions(
                user_id=user_id,
                positions=positions,
                tenant_id=tenant_id,
            )

            await self._session.commit()

            logger.info(
                "mock_portfolio_imported",
                user_id=str(user_id),
                positions=len(positions),
                total_value=round(total_value, 2),
            )

            return PortfolioCanonical(
                user_id=str(user_id),
                mode=PortfolioMode.MOCK_JSON,
                holdings=[PortfolioHolding(**p) for p in positions],
                total_value=total_value,
                cash_balance=cash_balance,
                last_synced_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            await self._session.rollback()
            logger.error(
                "portfolio_import_failed",
                user_id=str(user_id),
                error=str(e),
            )
            raise

    async def get_portfolio(self, user_id: uuid.UUID) -> PortfolioCanonical | None:
        """Retrieve the canonical portfolio for a user."""
        portfolio = await self._portfolio_repo.get_by_user(user_id)
        if not portfolio:
            return None

        holdings = []
        if portfolio.holdings and "items" in portfolio.holdings:
            for item in portfolio.holdings["items"]:
                holdings.append(PortfolioHolding(**item))

        return PortfolioCanonical(
            user_id=str(user_id),
            mode=portfolio.mode,
            holdings=holdings,
            total_value=portfolio.total_value,
            cash_balance=portfolio.cash_balance,
            last_synced_at=portfolio.last_synced_at,
            is_stale=portfolio.is_stale,
        )

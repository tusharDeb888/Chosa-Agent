"""
Seed Mock Portfolio — Populate demo user with sample Indian stock holdings.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


DEMO_HOLDINGS = [
    {"symbol": "RELIANCE", "quantity": 50, "avg_price": 2450.0, "sector": "Oil & Gas", "exchange": "NSE"},
    {"symbol": "TCS", "quantity": 25, "avg_price": 3800.0, "sector": "IT", "exchange": "NSE"},
    {"symbol": "INFY", "quantity": 100, "avg_price": 1550.0, "sector": "IT", "exchange": "NSE"},
    {"symbol": "HDFCBANK", "quantity": 60, "avg_price": 1650.0, "sector": "Banking", "exchange": "NSE"},
    {"symbol": "ICICIBANK", "quantity": 80, "avg_price": 1050.0, "sector": "Banking", "exchange": "NSE"},
    {"symbol": "SBIN", "quantity": 150, "avg_price": 620.0, "sector": "Banking", "exchange": "NSE"},
    {"symbol": "BHARTIARTL", "quantity": 40, "avg_price": 1180.0, "sector": "Telecom", "exchange": "NSE"},
    {"symbol": "ITC", "quantity": 200, "avg_price": 440.0, "sector": "FMCG", "exchange": "NSE"},
    {"symbol": "KOTAKBANK", "quantity": 30, "avg_price": 1760.0, "sector": "Banking", "exchange": "NSE"},
    {"symbol": "LT", "quantity": 20, "avg_price": 3400.0, "sector": "Infrastructure", "exchange": "NSE"},
]


async def seed():
    """Seed the database with a demo user and mock portfolio."""
    from app.db.engine import get_session_factory
    from app.db.repositories import UserRepository
    from app.portfolio.service import PortfolioService

    session_factory = get_session_factory()

    async with session_factory() as session:
        user_repo = UserRepository(session)

        # Create or get demo user
        user = await user_repo.get_by_email("demo@alphahunter.ai")
        if not user:
            user = await user_repo.create(
                email="demo@alphahunter.ai",
                name="Demo Trader",
                agent_state="PAUSED",
                risk_tolerance="moderate",
                portfolio_mode="MOCK_JSON",
                policy_constraints={
                    "max_position_concentration_pct": 25.0,
                    "max_daily_actions": 20,
                    "min_confidence_buy_sell": 60,
                    "max_evidence_age_hours": 24,
                },
            )
            await session.commit()
            print(f"✓ Created demo user: {user.id}")
        else:
            print(f"✓ Demo user exists: {user.id}")

        # Import mock portfolio
        portfolio_service = PortfolioService(session)
        portfolio = await portfolio_service.import_mock(
            user_id=user.id,
            holdings_data=DEMO_HOLDINGS,
            cash_balance=500000.0,
        )

        print(f"✓ Portfolio imported: {len(portfolio.holdings)} positions")
        print(f"  Total value: ₹{portfolio.total_value:,.2f}")
        print(f"  Cash balance: ₹{portfolio.cash_balance:,.2f}")

        # Set user to RUNNING so pipeline can process
        await user_repo.update_agent_state(user.id, "RUNNING")
        await session.commit()
        print(f"✓ User agent state set to RUNNING")


if __name__ == "__main__":
    asyncio.run(seed())

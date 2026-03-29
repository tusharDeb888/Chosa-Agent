"""
Market Data API — Real historical candles + market status + portfolio holdings.

Serves real Upstox data. No mock data.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.config import get_settings
from app.core.observability import get_logger
from app.ingestion.market_hours import get_market_status, get_last_trading_date

logger = get_logger("api.market")

router = APIRouter(prefix="/market")


@router.get("/instruments")
async def get_all_instruments():
    """Returns a list of all 9000+ NSE Equity standard symbols."""
    try:
        from app.ingestion.providers.upstox import get_instrument_details
        data = await get_instrument_details()
        return {"count": len(data), "instruments": data}
    except Exception as e:
        logger.error("api_fetch_instruments_failed", error=str(e))
        return {"count": 0, "instruments": []}


@router.get("/status")
async def market_status():
    """Get current NSE market status (open/closed/pre-market/post-market)."""
    return get_market_status()


@router.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    date: str | None = Query(None, description="Date in YYYY-MM-DD format. Defaults to last trading day."),
    interval: str = Query("1minute", description="Candle interval: 1minute, 30minute, day"),
):
    """Fetch real historical candle data from Upstox for a symbol."""
    settings = get_settings()

    if not settings.upstox_access_token:
        return {"error": "Upstox access token not configured", "candles": []}

    from app.ingestion.providers.upstox import UpstoxProvider

    provider = UpstoxProvider(
        api_key=settings.upstox_api_key,
        api_secret=settings.upstox_api_secret,
        access_token=settings.upstox_access_token,
    )

    try:
        candles = await provider.fetch_historical_candles(
            symbol=symbol.upper(),
            date=date or get_last_trading_date(),
            interval=interval,
        )
        return {
            "symbol": symbol.upper(),
            "date": date or get_last_trading_date(),
            "interval": interval,
            "count": len(candles),
            "candles": candles,
        }
    except Exception as e:
        logger.error("candle_fetch_error", symbol=symbol, error=str(e))
        return {"error": str(e), "candles": []}
    finally:
        await provider.close()


@router.get("/candles-batch")
async def get_candles_batch(
    symbols: str = Query("RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK", description="Comma-separated symbols"),
    date: str | None = Query(None),
    interval: str = Query("30minute"),
):
    """Fetch historical candles for multiple symbols at once."""
    settings = get_settings()

    if not settings.upstox_access_token:
        return {"error": "Upstox access token not configured", "data": {}}

    from app.ingestion.providers.upstox import UpstoxProvider

    provider = UpstoxProvider(
        api_key=settings.upstox_api_key,
        api_secret=settings.upstox_api_secret,
        access_token=settings.upstox_access_token,
    )

    target_date = date or get_last_trading_date()
    result = {}

    try:
        for symbol in symbols.split(","):
            symbol = symbol.strip().upper()
            if not symbol:
                continue
            candles = await provider.fetch_historical_candles(
                symbol=symbol,
                date=target_date,
                interval=interval,
            )
            if candles:
                result[symbol] = {
                    "count": len(candles),
                    "last_price": candles[0]["close"] if candles else None,
                    "day_high": max(c["high"] for c in candles) if candles else None,
                    "day_low": min(c["low"] for c in candles) if candles else None,
                    "total_volume": sum(c["volume"] for c in candles) if candles else 0,
                    "candles": candles,
                }
    except Exception as e:
        logger.error("batch_candle_error", error=str(e))
    finally:
        await provider.close()

    return {
        "date": target_date,
        "interval": interval,
        "market_status": get_market_status(),
        "data": result,
    }


@router.get("/history/{symbol}")
async def get_multi_day_history(
    symbol: str,
    days: int = Query(30, description="Number of past trading days to fetch"),
    interval: str = Query("day", description="Candle interval: 1minute, 30minute, day"),
):
    """Fetch multi-day historical candle data for chart displays."""
    settings = get_settings()

    if not settings.upstox_access_token:
        return {"error": "Upstox access token not configured", "candles": []}

    from app.ingestion.providers.upstox import UpstoxProvider

    provider = UpstoxProvider(
        api_key=settings.upstox_api_key,
        api_secret=settings.upstox_api_secret,
        access_token=settings.upstox_access_token,
    )

    try:
        from datetime import datetime, timedelta
        end_date = get_last_trading_date()
        # Go back enough calendar days to cover the requested trading days
        start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=int(days * 1.6))
        start_date = start_dt.strftime("%Y-%m-%d")

        candles = await provider.fetch_range_candles(
            symbol=symbol.upper(),
            from_date=start_date,
            to_date=end_date,
            interval=interval,
        )
        return {
            "symbol": symbol.upper(),
            "from_date": start_date,
            "to_date": end_date,
            "interval": interval,
            "count": len(candles),
            "candles": candles,
        }
    except Exception as e:
        logger.error("history_fetch_error", symbol=symbol, error=str(e))
        return {"error": str(e), "candles": []}
    finally:
        await provider.close()


@router.post("/portfolio-value")
async def get_portfolio_value(request: dict):
    """
    Calculate real-time portfolio value from user holdings.

    Expects: {"holdings": [{"symbol": "RELIANCE", "qty": 10, "buy_price": 1400.0}, ...]}
    Returns each holding enriched with latest Upstox price, P&L, day change.
    """
    settings = get_settings()

    if not settings.upstox_access_token:
        return {"error": "Upstox access token not configured"}

    holdings = request.get("holdings", [])
    if not holdings:
        return {"holdings": [], "total_invested": 0, "total_current": 0, "total_pnl": 0, "day_change": 0}

    symbols = [h["symbol"].upper() for h in holdings]
    symbols_str = ",".join(symbols)

    from app.ingestion.providers.upstox import UpstoxProvider

    provider = UpstoxProvider(
        api_key=settings.upstox_api_key,
        api_secret=settings.upstox_api_secret,
        access_token=settings.upstox_access_token,
    )

    try:
        target_date = get_last_trading_date()
        market_data = {}

        for symbol in symbols:
            candles = await provider.fetch_historical_candles(
                symbol=symbol, date=target_date, interval="30minute",
            )
            if candles:
                market_data[symbol] = {
                    "last_price": candles[0]["close"],
                    "day_open": candles[-1]["open"],
                    "day_high": max(c["high"] for c in candles),
                    "day_low": min(c["low"] for c in candles),
                    "total_volume": sum(c["volume"] for c in candles),
                    "candles": candles,
                }

        enriched = []
        total_invested = 0
        total_current = 0
        total_day_change_value = 0

        for h in holdings:
            sym = h["symbol"].upper()
            qty = h.get("qty", 0)
            buy_price = h.get("buy_price", 0)
            invested = qty * buy_price
            total_invested += invested

            md = market_data.get(sym)
            if md:
                current_price = md["last_price"]
                current_value = qty * current_price
                total_current += current_value
                pnl = current_value - invested
                pnl_pct = (pnl / invested * 100) if invested else 0
                day_open = md["day_open"]
                day_change = current_price - day_open
                day_change_pct = (day_change / day_open * 100) if day_open else 0
                total_day_change_value += day_change * qty

                enriched.append({
                    "symbol": sym,
                    "qty": qty,
                    "buy_price": buy_price,
                    "current_price": current_price,
                    "invested": round(invested, 2),
                    "current_value": round(current_value, 2),
                    "pnl": round(pnl, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "day_change": round(day_change, 2),
                    "day_change_pct": round(day_change_pct, 2),
                    "day_high": md["day_high"],
                    "day_low": md["day_low"],
                    "total_volume": md["total_volume"],
                    "candles": md["candles"],
                })
            else:
                total_current += invested
                enriched.append({
                    "symbol": sym,
                    "qty": qty,
                    "buy_price": buy_price,
                    "current_price": buy_price,
                    "invested": round(invested, 2),
                    "current_value": round(invested, 2),
                    "pnl": 0,
                    "pnl_pct": 0,
                    "day_change": 0,
                    "day_change_pct": 0,
                    "day_high": buy_price,
                    "day_low": buy_price,
                    "total_volume": 0,
                    "candles": [],
                })

        return {
            "date": target_date,
            "market_status": get_market_status(),
            "holdings": enriched,
            "total_invested": round(total_invested, 2),
            "total_current": round(total_current, 2),
            "total_pnl": round(total_current - total_invested, 2),
            "total_pnl_pct": round((total_current - total_invested) / total_invested * 100, 2) if total_invested else 0,
            "day_change": round(total_day_change_value, 2),
        }
    except Exception as e:
        logger.error("portfolio_value_error", error=str(e))
        return {"error": str(e)}
    finally:
        await provider.close()


@router.get("/holdings")
async def get_real_holdings():
    """Fetch real portfolio holdings from Upstox."""
    settings = get_settings()

    if not settings.upstox_access_token:
        return {"error": "Upstox access token not configured", "holdings": []}

    from app.ingestion.providers.upstox import UpstoxProvider

    provider = UpstoxProvider(
        api_key=settings.upstox_api_key,
        api_secret=settings.upstox_api_secret,
        access_token=settings.upstox_access_token,
    )

    try:
        holdings = await provider.fetch_holdings()
        positions = await provider.fetch_positions()

        return {
            "source": "upstox_live",
            "market_status": get_market_status(),
            "holdings": holdings,
            "positions": positions,
            "total_holdings": len(holdings),
            "total_positions": len(positions),
        }
    except Exception as e:
        logger.error("holdings_fetch_error", error=str(e))
        return {"error": str(e), "holdings": [], "positions": []}
    finally:
        await provider.close()

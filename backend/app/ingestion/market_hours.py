"""
Market Hours Utility — NSE/BSE trading session awareness.

NSE trading hours: 9:15 AM – 3:30 PM IST, Monday–Friday (excluding holidays).
"""

from __future__ import annotations

from datetime import datetime, time, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

# NSE market hours
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

# 2026 NSE holidays (approximate — includes major ones)
NSE_HOLIDAYS_2026 = {
    "2026-01-26",  # Republic Day
    "2026-03-10",  # Maha Shivaratri
    "2026-03-17",  # Holi
    "2026-03-31",  # Id-Ul-Fitr (Ramadan)
    "2026-04-02",  # Ram Navami
    "2026-04-03",  # Mahavir Jayanti
    "2026-04-14",  # Dr. Ambedkar Jayanti / Good Friday
    "2026-05-01",  # Maharashtra Day
    "2026-06-07",  # Bakrid
    "2026-07-06",  # Muharram
    "2026-08-15",  # Independence Day
    "2026-08-26",  # Janmashtami
    "2026-09-04",  # Milad-un-Nabi
    "2026-10-02",  # Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-10-21",  # Dussehra (cont.)
    "2026-11-09",  # Diwali (Laxmi Puja)
    "2026-11-10",  # Diwali (Balipratipada)
    "2026-11-30",  # Guru Nanak Jayanti
    "2026-12-25",  # Christmas
}


def is_market_open() -> bool:
    """Check if NSE is currently in trading session."""
    now = datetime.now(IST)

    # Weekend check
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False

    # Holiday check
    date_str = now.strftime("%Y-%m-%d")
    if date_str in NSE_HOLIDAYS_2026:
        return False

    # Time check
    current_time = now.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def get_last_trading_date() -> str:
    """Get the most recent trading date in YYYY-MM-DD format."""
    now = datetime.now(IST)
    dt = now.date()

    # If market is currently open, today is the last trading date
    if is_market_open():
        return dt.isoformat()

    # If today is a weekday and market already closed for the day, use today
    if now.weekday() < 5 and now.time() > MARKET_CLOSE:
        date_str = dt.isoformat()
        if date_str not in NSE_HOLIDAYS_2026:
            return date_str

    # Walk backward to find the last trading day
    for i in range(1, 10):
        candidate = dt - timedelta(days=i)
        if candidate.weekday() < 5:
            date_str = candidate.isoformat()
            if date_str not in NSE_HOLIDAYS_2026:
                return date_str

    return dt.isoformat()


def get_market_status() -> dict:
    """Get full market status info for frontend."""
    now = datetime.now(IST)
    open_flag = is_market_open()

    if open_flag:
        status = "OPEN"
        msg = "NSE is live"
    elif now.weekday() >= 5:
        status = "WEEKEND"
        msg = f"Market closed — {'Saturday' if now.weekday() == 5 else 'Sunday'}"
    elif now.time() < MARKET_OPEN:
        status = "PRE_MARKET"
        msg = f"Pre-market — opens at 9:15 AM IST"
    elif now.time() > MARKET_CLOSE:
        status = "POST_MARKET"
        msg = "Post-market — closed at 3:30 PM IST"
    else:
        status = "HOLIDAY"
        msg = "Market holiday"

    return {
        "is_open": open_flag,
        "status": status,
        "message": msg,
        "current_time_ist": now.strftime("%H:%M:%S"),
        "last_trading_date": get_last_trading_date(),
    }

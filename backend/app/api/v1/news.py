"""
Portfolio News API — 24/7 portfolio-relevant news feed.

Provides mock news during demo mode and live news via Finnhub in production.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from app.config import get_settings
from app.core.observability import get_logger

logger = get_logger("api.news")
router = APIRouter(prefix="/news")

# ── Mock news templates ──
MOCK_NEWS_TEMPLATES = [
    {
        "category": "news",
        "templates": [
            ("{ticker} Q{q} results beat street estimates, PAT up {pct}%", "bullish"),
            ("{ticker} reports strong revenue growth, management guides higher", "bullish"),
            ("{ticker} announces strategic partnership with global tech firm", "bullish"),
            ("{ticker} faces headwinds as sector sentiment weakens", "bearish"),
            ("{ticker} misses analyst expectations on margin pressure", "bearish"),
            ("{ticker} trading flat ahead of key policy announcement", "neutral"),
            ("{ticker} board appoints new CEO with strong track record", "bullish"),
            ("{ticker} under SEBI lens for compliance concerns", "bearish"),
            ("Analysts upgrade {ticker} citing improved outlook", "bullish"),
            ("Foreign investors reduce stake in {ticker} by {pct}%", "bearish"),
            ("{ticker} dividend yield attracts institutional interest", "bullish"),
            ("{ticker} capex guidance steady, no major surprises expected", "neutral"),
        ],
    },
    {
        "category": "filing",
        "templates": [
            ("{ticker} — Board approves interim dividend of ₹{div} per share", "bullish"),
            ("{ticker} — Promoter increases stake via open market purchase", "bullish"),
            ("{ticker} — Insider sale: CFO sells {qty} shares at ₹{price}", "bearish"),
            ("{ticker} — Annual General Meeting scheduled for {date}", "neutral"),
            ("{ticker} — Credit rating upgraded by CRISIL to {rating}", "bullish"),
            ("{ticker} — Buyback offer at premium of {pct}% to CMP", "bullish"),
            ("{ticker} — Preferential allotment approved by shareholders", "neutral"),
            ("{ticker} — Related party transaction: ₹{amt}Cr with subsidiary", "neutral"),
        ],
    },
    {
        "category": "macro",
        "templates": [
            ("RBI keeps repo rate unchanged at {rate}%, stance remains {stance}", "neutral"),
            ("India GDP growth at {pct}%, IMF raises forecast", "bullish"),
            ("FII outflows accelerate: ₹{amt}Cr sold in equity markets", "bearish"),
            ("INR strengthens against USD, export-heavy stocks under pressure", "bearish"),
            ("Government announces ₹{amt}L Cr infrastructure spending push", "bullish"),
            ("Crude oil prices surge {pct}%, energy stocks rally", "bullish"),
            ("IT sector braces for US recession fears, growth outlook cautious", "bearish"),
            ("Banking sector NPAs at decade low, credit growth robust", "bullish"),
            ("GST collections hit ₹{amt}L Cr — record high signals strong economy", "bullish"),
            ("India VIX spikes {pct}%, market volatility expected", "neutral"),
        ],
    },
]

MOCK_SOURCES = [
    "Economic Times", "Moneycontrol", "LiveMint", "Business Standard",
    "NDTV Profit", "Bloomberg Quint", "Reuters India", "BSE India",
    "NSE India", "SEBI Filings",
]

PORTFOLIO_TICKERS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "ITC", "SBIN", "BHARTIARTL", "BAJFINANCE", "LT",
    "HINDUNILVR", "ASIANPAINT", "MARUTI", "WIPRO", "AXISBANK",
]


def _generate_mock_news(
    holdings: list[str] | None = None,
    sentiment_filter: str = "all",
    category_filter: str = "all",
    count: int = 15,
) -> list[dict]:
    """Generate realistic mock financial news."""
    tickers = holdings or PORTFOLIO_TICKERS[:8]
    news_items = []
    now = datetime.now(timezone.utc)

    for i in range(count):
        cat_group = random.choice(MOCK_NEWS_TEMPLATES)
        template_entry = random.choice(cat_group["templates"])
        template, sentiment = template_entry

        ticker = random.choice(tickers)
        headline = template.format(
            ticker=ticker,
            pct=round(random.uniform(2, 28), 1),
            q=random.choice([1, 2, 3, 4]),
            div=random.choice([5, 8, 10, 12, 15, 20]),
            qty=random.randint(5000, 50000),
            price=random.randint(800, 3000),
            date=f"2026-{random.randint(4, 12):02d}-{random.randint(1, 28):02d}",
            rating=random.choice(["AA+", "AAA", "AA"]),
            amt=random.randint(50, 5000),
            rate=random.choice(["6.00", "6.25", "6.50"]),
            stance=random.choice(["accommodative", "neutral", "withdrawal"]),
        )

        if sentiment_filter != "all" and sentiment != sentiment_filter:
            continue

        if category_filter != "all" and cat_group["category"] != category_filter:
            continue

        minutes_ago = random.randint(1, 180)
        published = now - timedelta(minutes=minutes_ago)

        news_id = hashlib.md5(
            f"{ticker}-{headline[:30]}-{i}".encode()
        ).hexdigest()[:16]

        impact_score = random.randint(20, 95)
        if sentiment == "bearish":
            impact_score = max(impact_score, 50)
        elif sentiment == "bullish":
            impact_score = max(impact_score, 40)

        news_items.append({
            "id": news_id,
            "ticker": ticker,
            "headline": headline,
            "sentiment": sentiment,
            "source": random.choice(MOCK_SOURCES),
            "published_at": published.isoformat(),
            "fetched_at": now.isoformat(),
            "impact_score": impact_score,
            "category": cat_group["category"],
            "reasoning_id": f"explain-{news_id}",
            "source_mode": "mock",
            "url": f"https://example.com/news/{news_id}",
            "summary": headline,
        })

    # Sort by published_at descending
    news_items.sort(key=lambda x: x["published_at"], reverse=True)
    return news_items[:count]


async def _fetch_real_news(
    tickers: list[str],
    category: str = "all",
) -> list[dict]:
    """Fetch live news from free RSS sources (Google News, ET, Moneycontrol)."""
    import httpx
    import xml.etree.ElementTree as ET_xml
    import re

    news_items = []
    now = datetime.now(timezone.utc)

    # Google News RSS queries for Indian stocks
    queries = []
    ticker_map: dict[str, list[str]] = {}

    for ticker in tickers[:6]:
        q = f"{ticker} NSE stock"
        queries.append((q, ticker))
        ticker_map[ticker] = [ticker]

    # Always add macro/market queries
    queries.append(("Indian stock market NSE BSE", "MARKET"))
    queries.append(("RBI India economy GDP", "MACRO"))

    try:
        async with httpx.AsyncClient(
            timeout=12.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            },
            follow_redirects=True,
        ) as client:
            for query, ticker in queries:
                try:
                    encoded_q = query.replace(" ", "+")
                    rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=en-IN&gl=IN&ceid=IN:en"

                    resp = await client.get(rss_url)
                    if resp.status_code != 200:
                        continue

                    root = ET_xml.fromstring(resp.text)
                    channel = root.find("channel")
                    if channel is None:
                        continue

                    items = channel.findall("item")
                    for item in items[:8]:
                        headline = item.findtext("title", "").strip()
                        # Remove source suffix from Google News titles (e.g. " - Economic Times")
                        source_match = re.search(r"\s*-\s*([^-]+)$", headline)
                        source = source_match.group(1).strip() if source_match else "Google News"
                        if source_match:
                            headline = headline[: source_match.start()].strip()

                        if not headline:
                            continue

                        link = item.findtext("link", "")
                        pub_date_str = item.findtext("pubDate", "")

                        # Parse pub date
                        published = now
                        if pub_date_str:
                            try:
                                from email.utils import parsedate_to_datetime
                                published = parsedate_to_datetime(pub_date_str).replace(tzinfo=timezone.utc)
                            except Exception:
                                pass

                        # Skip articles older than 7 days
                        if (now - published).days > 7:
                            continue

                        sentiment = _classify_sentiment(headline)

                        # Determine category
                        cat = "news"
                        h_lower = headline.lower()
                        if any(w in h_lower for w in ["filing", "sec", "annual", "quarterly", "board", "dividend", "agm", "sebi"]):
                            cat = "filing"
                        elif any(w in h_lower for w in ["gdp", "rbi", "fed", "inflation", "policy", "economy", "fiscal", "budget", "trade"]):
                            cat = "macro"

                        if ticker in ("MARKET", "MACRO"):
                            cat = "macro"

                        if category != "all" and cat != category:
                            continue

                        # Map back to portfolio ticker
                        display_ticker = ticker if ticker not in ("MARKET", "MACRO") else "MARKET"

                        news_id = hashlib.md5(
                            f"{display_ticker}-{headline[:30]}-{pub_date_str}".encode()
                        ).hexdigest()[:16]

                        # Avoid duplicates
                        if any(n["id"] == news_id for n in news_items):
                            continue

                        impact_score = random.randint(30, 85)
                        if sentiment == "bearish":
                            impact_score = max(impact_score, 50)

                        news_items.append({
                            "id": news_id,
                            "ticker": display_ticker,
                            "headline": headline,
                            "sentiment": sentiment,
                            "source": source,
                            "published_at": published.isoformat(),
                            "fetched_at": now.isoformat(),
                            "impact_score": impact_score,
                            "category": cat,
                            "reasoning_id": f"explain-{news_id}",
                            "source_mode": "live",
                            "url": link,
                            "summary": headline,
                        })

                except Exception as e:
                    logger.warning("rss_ticker_error", ticker=ticker, error=str(e))
                    continue

    except Exception as e:
        logger.error("rss_connection_error", error=str(e))

    news_items.sort(key=lambda x: x["published_at"], reverse=True)
    return news_items


def _classify_sentiment(headline: str) -> str:
    """Simple keyword-based sentiment classification."""
    h = headline.lower()
    bullish = ["surge", "beat", "gain", "rally", "growth", "upgrade", "record", "strong", "profit", "rise", "high", "dividend", "buyback", "positive"]
    bearish = ["fall", "drop", "miss", "decline", "loss", "downgrade", "concern", "weak", "pressure", "sell", "cut", "warning", "risk", "negative", "probe"]

    bull_count = sum(1 for w in bullish if w in h)
    bear_count = sum(1 for w in bearish if w in h)

    if bull_count > bear_count:
        return "bullish"
    elif bear_count > bull_count:
        return "bearish"
    return "neutral"


@router.get("/portfolio")
async def get_portfolio_news(
    window: str = Query(default="180m", description="Time window e.g. 60m, 180m, 24h"),
    sentiment: str = Query(default="all", description="all|bullish|bearish|neutral"),
    holdings_only: bool = Query(default=False, description="Filter to portfolio holdings only"),
    category: str = Query(default="all", description="all|news|filing|macro"),
    mode: str = Query(default="live", description="live|mock — live uses Google News RSS (free, no key)"),
):
    """
    24/7 Portfolio News Radar endpoint.

    Returns portfolio-relevant news from Google News RSS (live, free)
    or mock generator as fallback.
    """

    # Determine holdings
    holdings = PORTFOLIO_TICKERS[:8]

    news_items = []

    # Always try live first (uses free RSS, no API key needed)
    if mode != "mock":
        news_items = await _fetch_real_news(
            tickers=holdings,
            category=category,
        )

    # Fallback to mock if live returned nothing or mode is mock
    if not news_items:
        news_items = _generate_mock_news(
            holdings=holdings,
            sentiment_filter=sentiment,
            category_filter=category,
            count=20,
        )

    # Filter by sentiment
    if sentiment != "all":
        news_items = [n for n in news_items if n["sentiment"] == sentiment]

    # Filter by holdings only
    if holdings_only:
        news_items = [n for n in news_items if n["ticker"] in holdings]

    actual_mode = "live" if news_items and news_items[0].get("source_mode") == "live" else "mock"

    return {
        "items": news_items,
        "count": len(news_items),
        "source_mode": actual_mode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

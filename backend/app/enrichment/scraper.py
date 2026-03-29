"""
Web Scraper — Crawl4AI async evidence extraction.

Allowlist-only domains, concurrency caps, freshness tagging.
Fallback: returns empty list on failure (caller handles degradation).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings
from app.core.schemas import EvidenceItem
from app.core.observability import get_logger, traced

logger = get_logger("enrichment.scraper")


@traced("enrichment.scrape")
async def scrape_for_symbol(
    symbol: str,
    max_results: int = 5,
) -> list[EvidenceItem]:
    """
    Scrape news and analysis for a stock symbol from allowlisted domains.

    Phase 1: Simplified — generates search URLs and attempts scraping.
    Returns EvidenceItems with provenance metadata.
    """
    settings = get_settings()
    domains = settings.allowed_domains_list
    items: list[EvidenceItem] = []

    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
        )

        run_config = CrawlerRunConfig(
            word_count_threshold=50,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            for domain in domains[:3]:  # Limit to 3 domains per signal
                url = f"https://www.google.com/search?q={symbol}+stock+NSE+site:{domain}"

                try:
                    result = await crawler.arun(
                        url=url,
                        config=run_config,
                    )

                    if result and result.success and result.markdown:
                        items.append(
                            EvidenceItem(
                                source_url=url,
                                title=f"{symbol} news from {domain}",
                                content=result.markdown[:2000],
                                fetched_at=datetime.now(timezone.utc),
                                reliability_score=0.6,
                                source_type="web",
                            )
                        )

                except Exception as e:
                    logger.debug(
                        "domain_scrape_failed",
                        domain=domain,
                        symbol=symbol,
                        error=str(e),
                    )

    except ImportError:
        logger.warning("crawl4ai_not_available", symbol=symbol)
    except Exception as e:
        logger.error("scraper_failed", symbol=symbol, error=str(e))

    return items[:max_results]

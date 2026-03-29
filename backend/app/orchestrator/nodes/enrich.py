"""
Enrich Node — Context enrichment for the decision pipeline.

Phase 1: Simplified evidence retrieval (web scraping + vector memory fallback).
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.schemas import EvidencePack, EvidenceItem
from app.core.observability import get_logger, traced
from app.orchestrator.state import AgentGraphState

logger = get_logger("orchestrator.nodes.enrich")


@traced("node.enrich")
async def enrich_node(state: AgentGraphState) -> dict:
    """
    Gather evidence for the signal from:
    1. Corporate filings (BSE/NSE/RBI) — highest reliability
    2. Web scraping (Crawl4AI) — allowlisted domains
    3. Vector memory (pgvector) — historical context

    On failure: fallback to vector-only with degraded_context=true.
    """
    signal = state["signal"]
    symbol = signal.symbol

    evidence_items = []
    degraded = False
    sources_attempted = 0
    sources_succeeded = 0

    # ── Source 1: Corporate filings (highest reliability) ──
    try:
        from app.enrichment.filing_scraper import fetch_corporate_filings, filings_to_evidence
        sources_attempted += 1
        filings = await fetch_corporate_filings(symbol, max_results=3)
        if filings:
            filing_evidence = filings_to_evidence(filings)
            evidence_items.extend(filing_evidence)
            sources_succeeded += 1
            logger.info(
                "filing_evidence_added",
                symbol=symbol,
                filing_count=len(filings),
                types=[f.filing_type for f in filings],
            )
    except Exception as e:
        logger.warning(
            "filing_fetch_failed",
            symbol=symbol,
            error=str(e),
        )

    # ── Source 2: Web scraping ──
    try:
        from app.enrichment.scraper import scrape_for_symbol
        sources_attempted += 1
        web_items = await scrape_for_symbol(symbol)
        evidence_items.extend(web_items)
        sources_succeeded += 1
    except Exception as e:
        logger.warning(
            "web_scraping_failed",
            symbol=symbol,
            error=str(e),
        )
        degraded = True

    # ── Source 3: Vector memory retrieval ──
    try:
        from app.enrichment.retriever import retrieve_knowledge
        sources_attempted += 1
        memory_items = await retrieve_knowledge(symbol)
        evidence_items.extend(memory_items)
        sources_succeeded += 1
    except Exception as e:
        logger.warning(
            "vector_retrieval_failed",
            symbol=symbol,
            error=str(e),
        )

    # ── If nothing, add a placeholder ──
    if not evidence_items:
        degraded = True
        evidence_items.append(
            EvidenceItem(
                source_url="internal://anomaly-detector",
                title=f"Anomaly detected for {symbol}",
                content=(
                    f"Volume z-score: {signal.z_score:.2f}, "
                    f"VWAP deviation: {signal.vwap_deviation_pct:.2f}%, "
                    f"Type: {signal.anomaly_type}"
                ),
                fetched_at=datetime.now(timezone.utc),
                reliability_score=0.3,
                source_type="internal",
            )
        )

    # Calculate freshness score
    freshness = 0.5
    if evidence_items:
        fresh_count = sum(
            1 for item in evidence_items
            if item.published_at and (datetime.now(timezone.utc) - item.published_at.replace(tzinfo=timezone.utc)).total_seconds() < 3600
        )
        freshness = fresh_count / len(evidence_items) if evidence_items else 0.5

    pack = EvidencePack(
        items=evidence_items,
        degraded_context=degraded,
        total_sources_attempted=sources_attempted,
        total_sources_succeeded=sources_succeeded,
        freshness_score=round(freshness, 2),
    )

    logger.info(
        "enrichment_complete",
        symbol=symbol,
        evidence_count=len(evidence_items),
        degraded=degraded,
        filing_sources=len([i for i in evidence_items if i.source_type == "corporate_filing"]),
    )

    return {"evidence_pack": pack}

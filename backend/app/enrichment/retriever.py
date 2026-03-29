"""
Knowledge Retriever — pgvector similarity search for historical context.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.schemas import EvidenceItem
from app.core.observability import get_logger, traced
from app.db.engine import get_session_factory
from app.db.repositories import KnowledgeRepository

logger = get_logger("enrichment.retriever")


@traced("enrichment.retrieve")
async def retrieve_knowledge(
    symbol: str,
    limit: int = 5,
) -> list[EvidenceItem]:
    """
    Retrieve relevant historical context from the knowledge base.

    Uses pgvector for semantic search with recency weighting.
    """
    items = []

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            repo = KnowledgeRepository(session)
            results = await repo.search_by_ticker(symbol, limit=limit)

            for entry in results:
                items.append(
                    EvidenceItem(
                        source_url=entry.source_url,
                        title=entry.title or f"Historical context for {symbol}",
                        content=entry.content[:2000],
                        published_at=entry.published_at,
                        fetched_at=entry.fetched_at or datetime.now(timezone.utc),
                        reliability_score=entry.reliability_score or 0.5,
                        source_type="vector_memory",
                    )
                )

    except Exception as e:
        logger.error("knowledge_retrieval_failed", symbol=symbol, error=str(e))

    return items

import json
import logging
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.query_cache import QueryCacheEntry

logger = logging.getLogger("rag_semantic_cache")

# A cache hit returns a previously generated answer verbatim, so this stays tight —
# it's meant to catch near-identical rephrasings, not merely related questions.
LOOKUP_THRESHOLD = 0.95
DEDUP_THRESHOLD = 0.97


class SemanticCache:
    """Per-user cache of (query -> answer) pairs, keyed by embedding similarity rather
    than exact text match. Scoped per-user (not global) because the MAG memory layer
    personalizes answers — a shared cache would leak one user's personalized answer to
    another. Reuses the embedding model already loaded by VectorStore."""

    def __init__(self, embeddings):
        self.embeddings = embeddings

    async def lookup(
        self, db: AsyncSession, user_id: int, query: str, threshold: float = LOOKUP_THRESHOLD
    ) -> Optional[Dict[str, Any]]:
        result = await db.execute(select(QueryCacheEntry).where(QueryCacheEntry.user_id == user_id))
        rows = result.scalars().all()
        if not rows:
            return None

        query_emb = np.array(self.embeddings.embed_query(query))
        cached_embs = np.array([json.loads(r.embedding) for r in rows])
        # embeddings are normalized (normalize_embeddings=True), so dot product == cosine similarity
        sims = cached_embs @ query_emb
        best_idx = int(np.argmax(sims))
        if float(sims[best_idx]) < threshold:
            return None

        row = rows[best_idx]
        return {
            "answer": row.answer,
            "sources": json.loads(row.sources),
            "confidence": row.confidence,
            "warning": row.warning,
        }

    async def store(
        self,
        db: AsyncSession,
        user_id: int,
        query: str,
        answer: str,
        sources: List[Dict[str, Any]],
        confidence: int,
        warning: Optional[str],
    ) -> None:
        if await self.lookup(db, user_id, query, threshold=DEDUP_THRESHOLD) is not None:
            return  # a near-duplicate is already cached

        query_emb = self.embeddings.embed_query(query)
        db.add(
            QueryCacheEntry(
                user_id=user_id,
                query=query,
                embedding=json.dumps(query_emb),
                answer=answer,
                # some source dicts carry numpy floats (BM25 scores) — default=float coerces
                # any non-JSON-native numeric type instead of raising
                sources=json.dumps(sources, default=float),
                confidence=confidence,
                warning=warning,
            )
        )
        await db.commit()

    async def clear(self, db: AsyncSession) -> None:
        await db.execute(delete(QueryCacheEntry))
        await db.commit()

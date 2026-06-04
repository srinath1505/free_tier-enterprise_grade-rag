import math
import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.core.limiter import limiter
from backend.engine.retriever import HybridRetriever
from backend.engine.vector_store import VectorStore
from backend.engine.llm import get_llm, LLMError
from backend.engine.query_expander import QueryExpander
from backend.engine.reranker import Reranker
from backend.security.sanitizer import InputSanitizer
from backend.security.guardrails import SecurityLayer, SecurityException
from backend.security.hallucination import HallucinationDetector
from backend.security.auth import get_current_user, User
from backend.core.observability import MetricsLogger
from backend.models.user import User as DBUser
from backend.api.endpoints.history import save_message

from backend.core.config import settings

router = APIRouter()

# Global singletons — initialised once on first request
_vector_store = None
_retriever = None
_reranker = None
_expander = None


def get_vector_store():
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever(get_vector_store())
    return _retriever


def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def get_expander():
    global _expander
    if _expander is None:
        _expander = QueryExpander()
    return _expander


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    alpha: float = 0.5
    use_query_expansion: bool = True


def _compute_confidence(
    ranked_docs: list,
    grounding_score: float,
    is_grounded: bool,
) -> int:
    """
    Multi-signal confidence score (0-100).

    Signals:
      - Reranker top logit  (60 %) : how relevant the best retrieved chunk is
      - Grounding score     (35 %) : how well the answer is supported by context
      - Source count bonus  ( 5 %) : more agreeing sources → more confident
    A penalty is applied when the hallucination detector flags the answer.
    """
    if not ranked_docs:
        return 0

    top_logit   = ranked_docs[0].get("rerank_score", 0.0)
    # Temperature-scaled sigmoid (T=3) maps ms-marco logits to a meaningful [0,100] range.
    # Raw sigmoid gives near-0% for any negative logit (e.g. -5 → 0.67%); T=3 gives 16%,
    # which better reflects that a retrieved doc has some—if low—relevance.
    rerank_pct  = 100.0 / (1.0 + math.exp(-top_logit / 3.0))
    ground_pct  = max(0.0, min(grounding_score, 1.0)) * 100.0
    count_bonus = min(len(ranked_docs) * 2, 6)

    raw = 0.60 * rerank_pct + 0.35 * ground_pct + count_bonus

    if not is_grounded:
        raw *= 0.75

    return round(min(max(raw, 0), 100))


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    confidence: int = 0
    warning: Optional[str] = None
    user: str


@router.post("/query", response_model=QueryResponse)
@limiter.limit(f"{settings.RATE_LIMIT_QUERY_PER_MIN}/minute")
async def query_rag(
    request: Request,
    body: QueryRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: Reranker = Depends(get_reranker),
    expander: QueryExpander = Depends(get_expander),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start_time = time.time()
    try:
        # 0. Sanitize & guardrails
        clean_query = InputSanitizer().sanitize(body.query)
        try:
            SecurityLayer().validate(clean_query)
        except SecurityException as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 1. Query expansion — skip silently if LLM is offline (avoids a wasted
        #    connection attempt before the answer-generation call also fails)
        queries_to_run = [clean_query]
        if body.use_query_expansion:
            try:
                queries_to_run.extend(expander.generate_variations(clean_query))
            except LLMError:
                pass  # LLM unreachable — proceed with original query only

        # 2. Hybrid retrieval — multi-query with dedup
        all_docs_map: Dict[Any, Dict] = {}
        k_per_query = 5 if body.use_query_expansion else 10
        for q in queries_to_run:
            for d in retriever.search(q, k=k_per_query, alpha=body.alpha):
                doc_id = d.get("id", hash(d.get("content", "")))
                if doc_id not in all_docs_map:
                    all_docs_map[doc_id] = d

        # 3. Rerank → top 3
        ranked_docs = reranker.rerank(clean_query, list(all_docs_map.values()), top_k=3)

        # 4. Build context
        context = (
            "\n\n".join(
                f"Source ({d.get('id', 'unknown')}): {d.get('content', '')}"
                for d in ranked_docs
            )
            if ranked_docs
            else "No relevant documents found."
        )

        # 5. Generate
        system_prompt = (
            f"You are a helpful assistant. Use the following context to answer the user request."
            f"\nContext:\n{context}"
        )
        try:
            answer = get_llm().generate(body.query, system_prompt=system_prompt)
        except LLMError as e:
            raise HTTPException(status_code=503, detail=str(e))

        # 6. Hallucination check
        context_text = [d.get("content", "") for d in ranked_docs]
        is_grounded, score, _ = HallucinationDetector().check_grounding(answer, context_text)
        warning = (
            f"Confidence Low: Answer may not be fully grounded in context (Score: {score:.2f})"
            if not is_grounded
            else None
        )

        # 7. Persist chat history
        db_result = await db.execute(select(DBUser).where(DBUser.username == current_user.username))
        db_user = db_result.scalar_one_or_none()
        if db_user:
            session_id = current_user.username
            await save_message(db, db_user.id, session_id, "user", body.query)
            await save_message(db, db_user.id, session_id, "assistant", answer)

        # 8. Metrics
        latency = (time.time() - start_time) * 1000
        MetricsLogger.log_request(
            endpoint="rag_query",
            user=current_user.username,
            latency_ms=latency,
            success=True,
            metadata={
                "query_len": len(body.query),
                "answer_len": len(answer),
                "hallucination_score": score,
                "blocked": False,
                "reranked_count": len(ranked_docs),
                "expansion_strategies": len(queries_to_run),
            },
        )

        confidence = _compute_confidence(ranked_docs, score, is_grounded)

        # 9. Log query for analytics
        from backend.models.query_log import QueryLog
        latency_final = (time.time() - start_time) * 1000
        db.add(QueryLog(user=current_user.username, query=body.query, response_time_ms=latency_final, success=True))
        await db.commit()

        return QueryResponse(answer=answer, sources=ranked_docs, confidence=confidence, warning=warning, user=current_user.username)

    except HTTPException as http_exc:
        from backend.models.query_log import QueryLog
        db.add(QueryLog(user=getattr(current_user, "username", "unknown"), query=body.query, response_time_ms=(time.time() - start_time) * 1000, success=False))
        await db.commit()
        raise http_exc
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

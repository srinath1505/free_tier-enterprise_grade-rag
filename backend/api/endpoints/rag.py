import json
import math
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
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
from backend.engine.memory import MemoryManager
from backend.engine.semantic_cache import SemanticCache
from backend.security.sanitizer import InputSanitizer
from backend.security.guardrails import SecurityLayer, SecurityException
from backend.security.hallucination import HallucinationDetector
from backend.security.auth import get_current_user, User
from backend.core.observability import MetricsLogger
from backend.models.user import User as DBUser
from backend.models.conversation import Conversation
from backend.api.endpoints.history import save_message

from backend.core.config import settings

router = APIRouter()

# Global singletons — initialised once on first request
_vector_store = None
_retriever = None
_reranker = None
_expander = None
_memory_manager = None
_semantic_cache = None


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


def get_expander(vector_store: VectorStore = Depends(get_vector_store)):
    global _expander
    if _expander is None:
        _expander = QueryExpander(vector_store.embeddings)
    return _expander


def get_memory_manager(vector_store: VectorStore = Depends(get_vector_store)):
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager(vector_store.embeddings)
    return _memory_manager


def get_semantic_cache(vector_store: VectorStore = Depends(get_vector_store)):
    global _semantic_cache
    if _semantic_cache is None:
        _semantic_cache = SemanticCache(vector_store.embeddings)
    return _semantic_cache


async def _get_recent_turns(db: AsyncSession, user_id: int, session_id: str, exchanges: int = 3) -> list:
    """Last N exchanges (2N rows) for this session, oldest first, as 'role: content' strings."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.session_id == session_id)
        .order_by(Conversation.timestamp.desc())
        .limit(exchanges * 2)
    )
    rows = list(reversed(result.scalars().all()))
    return [f"{r.role}: {r.content}" for r in rows]


async def _extract_and_store_memory(
    memory_manager: MemoryManager, db: AsyncSession, user_id: int, query: str, answer: str
) -> None:
    facts = memory_manager.extract_facts(query, answer)
    await memory_manager.upsert_facts(db, user_id, facts)


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


@dataclass
class PreparedQuery:
    """Everything the /query and /query/stream handlers need in common — retrieval,
    reranking, and prompt assembly, shared so the two endpoints don't duplicate the
    guardrail/contextualization/memory/cache-lookup pipeline."""
    clean_query: str
    contextualized_query: str
    db_user: Optional[DBUser]
    session_id: str
    ranked_docs: list = field(default_factory=list)
    system_prompt: str = ""
    queries_to_run: list = field(default_factory=list)
    cache_hit: Optional[Dict[str, Any]] = None


async def _prepare_query(
    body: QueryRequest,
    current_user: User,
    db: AsyncSession,
    retriever: HybridRetriever,
    reranker: Reranker,
    expander: QueryExpander,
    memory_manager: MemoryManager,
    cache: SemanticCache,
) -> PreparedQuery:
    # 0. Sanitize & guardrails
    clean_query = InputSanitizer().sanitize(body.query)
    try:
        SecurityLayer().validate(clean_query)
    except SecurityException as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 0.5 Resolve the DB user once — needed for memory, cache, and history persistence
    db_result = await db.execute(select(DBUser).where(DBUser.username == current_user.username))
    db_user = db_result.scalar_one_or_none()
    session_id = current_user.username

    # 0.6 Semantic cache, checked against the raw query first — a repeated/near-identical
    #     question should hit cache without paying for the contextualization LLM call below.
    #     Scoped per-user since answers are personalized by long-term memory further down.
    cache_hit = None
    if db_user:
        cache_hit = await cache.lookup(db, db_user.id, clean_query)
    if cache_hit:
        return PreparedQuery(clean_query, clean_query, db_user, session_id, cache_hit=cache_hit)

    # 0.7 Short-term memory — rewrite follow-up questions ("what about its performance?")
    #     into standalone queries using recent turns, so retrieval isn't blind to context
    recent_turns: list = []
    if db_user:
        recent_turns = await _get_recent_turns(db, db_user.id, session_id)
    contextualized_query = expander.contextualize(clean_query, recent_turns) if recent_turns else clean_query

    # 0.75 Second cache check — the contextualized form may match a previously cached
    #      fully-resolved question even when the raw follow-up phrasing didn't.
    if contextualized_query != clean_query:
        cache_hit = await cache.lookup(db, db_user.id, contextualized_query) if db_user else None
        if cache_hit:
            return PreparedQuery(clean_query, contextualized_query, db_user, session_id, cache_hit=cache_hit)

    # 0.8 Long-term memory — durable facts/preferences about this user
    relevant_memories: list = []
    if db_user:
        relevant_memories = await memory_manager.get_relevant(db, db_user.id, contextualized_query)

    # 1. Query expansion — skip silently if LLM is offline (avoids a wasted
    #    connection attempt before the answer-generation call also fails)
    queries_to_run = [contextualized_query]
    if body.use_query_expansion:
        try:
            queries_to_run.extend(expander.generate_variations(contextualized_query))
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
    ranked_docs = reranker.rerank(contextualized_query, list(all_docs_map.values()), top_k=3)

    # 4. Build context + system prompt
    context = (
        "\n\n".join(
            f"Source ({d.get('id', 'unknown')}): {d.get('content', '')}"
            for d in ranked_docs
        )
        if ranked_docs
        else "No relevant documents found."
    )
    memory_section = (
        "\n\nWhat you know about this user (may be empty):\n"
        + "\n".join(f"- {m}" for m in relevant_memories)
        if relevant_memories
        else ""
    )
    system_prompt = (
        f"You are a helpful assistant. Use the following context to answer the user request."
        f"\nContext:\n{context}"
        f"{memory_section}"
    )

    return PreparedQuery(
        clean_query, contextualized_query, db_user, session_id,
        ranked_docs=ranked_docs, system_prompt=system_prompt, queries_to_run=queries_to_run,
    )


async def _finalize(
    background_tasks: BackgroundTasks,
    memory_manager: MemoryManager,
    cache: SemanticCache,
    db: AsyncSession,
    current_user: User,
    prepared: PreparedQuery,
    original_query: str,
    answer: str,
    sources: list,
    confidence: int,
    warning: Optional[str],
    cached: bool,
    hallucination_score: Optional[float],
    start_time: float,
) -> None:
    """Shared tail of both endpoints: persist history, schedule MAG memory extraction,
    cache a fresh (non-cached) result, and log metrics/analytics."""
    if prepared.db_user:
        await save_message(db, prepared.db_user.id, prepared.session_id, "user", original_query)
        await save_message(db, prepared.db_user.id, prepared.session_id, "assistant", answer)
        background_tasks.add_task(
            _extract_and_store_memory, memory_manager, db, prepared.db_user.id, original_query, answer
        )
        if not cached:
            background_tasks.add_task(
                cache.store, db, prepared.db_user.id, prepared.contextualized_query,
                answer, sources, confidence, warning,
            )

    latency = (time.time() - start_time) * 1000
    MetricsLogger.log_request(
        endpoint="rag_query",
        user=current_user.username,
        latency_ms=latency,
        success=True,
        metadata={
            "query_len": len(original_query),
            "answer_len": len(answer),
            "hallucination_score": hallucination_score,
            "blocked": False,
            "reranked_count": len(sources),
            "expansion_strategies": len(prepared.queries_to_run),
            "cached": cached,
        },
    )

    from backend.models.query_log import QueryLog
    db.add(QueryLog(user=current_user.username, query=original_query, response_time_ms=latency, success=True))
    await db.commit()


@router.post("/query", response_model=QueryResponse)
@limiter.limit(f"{settings.RATE_LIMIT_QUERY_PER_MIN}/minute")
async def query_rag(
    request: Request,
    body: QueryRequest,
    background_tasks: BackgroundTasks,
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: Reranker = Depends(get_reranker),
    expander: QueryExpander = Depends(get_expander),
    memory_manager: MemoryManager = Depends(get_memory_manager),
    cache: SemanticCache = Depends(get_semantic_cache),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start_time = time.time()
    try:
        prepared = await _prepare_query(body, current_user, db, retriever, reranker, expander, memory_manager, cache)

        hallucination_score: Optional[float] = None
        if prepared.cache_hit:
            answer     = prepared.cache_hit["answer"]
            sources    = prepared.cache_hit["sources"]
            confidence = prepared.cache_hit["confidence"]
            warning    = prepared.cache_hit["warning"]
            cached = True
        else:
            try:
                answer = get_llm().generate(body.query, system_prompt=prepared.system_prompt)
            except LLMError as e:
                raise HTTPException(status_code=503, detail=str(e))

            context_text = [d.get("content", "") for d in prepared.ranked_docs]
            is_grounded, hallucination_score, _ = HallucinationDetector().check_grounding(answer, context_text)
            warning = (
                f"Confidence Low: Answer may not be fully grounded in context (Score: {hallucination_score:.2f})"
                if not is_grounded
                else None
            )
            confidence = _compute_confidence(prepared.ranked_docs, hallucination_score, is_grounded)
            sources = prepared.ranked_docs
            cached = False

        await _finalize(
            background_tasks, memory_manager, cache, db, current_user, prepared,
            body.query, answer, sources, confidence, warning, cached, hallucination_score, start_time,
        )

        return QueryResponse(answer=answer, sources=sources, confidence=confidence, warning=warning, user=current_user.username)

    except HTTPException as http_exc:
        from backend.models.query_log import QueryLog
        db.add(QueryLog(user=getattr(current_user, "username", "unknown"), query=body.query, response_time_ms=(time.time() - start_time) * 1000, success=False))
        await db.commit()
        raise http_exc
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
@limiter.limit(f"{settings.RATE_LIMIT_QUERY_PER_MIN}/minute")
async def query_rag_stream(
    request: Request,
    body: QueryRequest,
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: Reranker = Depends(get_reranker),
    expander: QueryExpander = Depends(get_expander),
    memory_manager: MemoryManager = Depends(get_memory_manager),
    cache: SemanticCache = Depends(get_semantic_cache),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events variant of /query. Emits `event: token` frames as the answer is
    generated, then a final `event: done` frame with sources/confidence/warning once the
    full answer is known (those signals require the complete text, so they can't stream)."""
    start_time = time.time()
    try:
        prepared = await _prepare_query(body, current_user, db, retriever, reranker, expander, memory_manager, cache)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    background_tasks = BackgroundTasks()

    async def event_stream():
        hallucination_score: Optional[float] = None
        if prepared.cache_hit:
            answer     = prepared.cache_hit["answer"]
            sources    = prepared.cache_hit["sources"]
            confidence = prepared.cache_hit["confidence"]
            warning    = prepared.cache_hit["warning"]
            cached = True
            yield f"event: token\ndata: {json.dumps(answer)}\n\n"
        else:
            chunks: List[str] = []
            try:
                for token in get_llm().generate_stream(body.query, system_prompt=prepared.system_prompt):
                    chunks.append(token)
                    yield f"event: token\ndata: {json.dumps(token)}\n\n"
            except LLMError as e:
                yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
                return

            answer = "".join(chunks)
            context_text = [d.get("content", "") for d in prepared.ranked_docs]
            is_grounded, hallucination_score, _ = HallucinationDetector().check_grounding(answer, context_text)
            warning = (
                f"Confidence Low: Answer may not be fully grounded in context (Score: {hallucination_score:.2f})"
                if not is_grounded
                else None
            )
            confidence = _compute_confidence(prepared.ranked_docs, hallucination_score, is_grounded)
            sources = prepared.ranked_docs
            cached = False

        await _finalize(
            background_tasks, memory_manager, cache, db, current_user, prepared,
            body.query, answer, sources, confidence, warning, cached, hallucination_score, start_time,
        )

        done_payload = {"confidence": confidence, "warning": warning, "sources": sources, "cached": cached}
        yield f"event: done\ndata: {json.dumps(done_payload, default=float)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", background=background_tasks)

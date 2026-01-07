from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from backend.engine.retriever import HybridRetriever
from backend.engine.vector_store import VectorStore
from backend.engine.llm import get_llm, LLMProvider
from backend.security.sanitizer import InputSanitizer
from backend.security.guardrails import SecurityLayer, SecurityException
import time
from backend.security.hallucination import HallucinationDetector
from backend.core.observability import MetricsLogger, setup_langsmith
from backend.security.auth import get_current_user, User

router = APIRouter()

# Dependency override for testing/singleton
# In a real app, use lru_cache or a proper dependency injection container
from backend.engine.query_expander import QueryExpander
from backend.engine.reranker import Reranker

# Global Singletons
_vector_store = None
_retriever = None
_reranker = None
_expander = None

def get_retriever():
    global _vector_store, _retriever
    if _retriever is None:
        if _vector_store is None:
            _vector_store = VectorStore()
        _retriever = HybridRetriever(_vector_store)
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
    use_query_expansion: bool = True # Enable by default for max accuracy

class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    warning: Optional[str] = None
    user: str 

@router.post("/query", response_model=QueryResponse)
def query_rag(
    request: QueryRequest, 
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: Reranker = Depends(get_reranker),
    expander: QueryExpander = Depends(get_expander),
    current_user: User = Depends(get_current_user)
):
    start_time = time.time()
    try:
        # 0. Safety & Security Checks
        # a. Sanitize PII
        sanitizer = InputSanitizer()
        clean_query = sanitizer.sanitize(request.query)
        
        # b. Validate & Guardrails
        security_layer = SecurityLayer()
        try:
            security_layer.validate(clean_query)
        except SecurityException as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # 1. Query Expansion (Optional)
        queries_to_run = [clean_query]
        if request.use_query_expansion:
            # Generate variations (High Latency Step)
            variations = expander.generate_variations(clean_query)
            queries_to_run.extend(variations)
        
        # 2. Retrieve (High Recall) - Multi-Query Dedup
        all_docs_map = {}
        
        # We fetch fewer docs per query since we run multiple queries
        # k=10 per query * 4 queries = 40 candidates. 
        # Reduced k to 5 per query to keep total pool size manageable for reranker
        k_per_query = 5 if request.use_query_expansion else 10
        
        for q in queries_to_run:
            docs = retriever.search(q, k=k_per_query, alpha=request.alpha)
            for d in docs:
                # Use source + info as ID, or hash content
                doc_id = d.get('id', hash(d.get('content', '')))
                if doc_id not in all_docs_map:
                    all_docs_map[doc_id] = d
        
        initial_docs = list(all_docs_map.values())
        
        # 3. Rerank (High Precision)
        # Narrow down to Top 3 for LLM Generation
        # We rerank against the ORIGINAL query to ensure relevance to user intent
        ranked_docs = reranker.rerank(clean_query, initial_docs, top_k=3)
        
        # 4. Context Construction
        if not ranked_docs:
            context = "No relevant documents found."
        else:
            context = "\n\n".join([f"Source ({d.get('id', 'unknown')}): {d.get('content', '')}" for d in ranked_docs])
        
        # 5. Generate
        system_prompt = f"You are a helpful assistant. Use the following context to answer the user request. \nContext:\n{context}"
        
        llm = get_llm()
        answer = llm.generate(request.query, system_prompt=system_prompt)
        
        # 6. Hallucination Check
        detector = HallucinationDetector()
        context_text = [doc.get('content', '') for doc in ranked_docs]
        is_grounded, score, reason = detector.check_grounding(answer, context_text)
        
        warning = None
        if not is_grounded:
            warning = f"Confidence Low: Answer may not be fully grounded in context (Score: {score:.2f})"
        
        
        # 7. Observability logging
        end_time = time.time()
        latency = (end_time - start_time) * 1000
        MetricsLogger.log_request(
            endpoint="rag_query",
            user=current_user.username,
            latency_ms=latency,
            success=True,
            metadata={
                "query_len": len(request.query),
                "answer_len": len(answer),
                "hallucination_score": score,
                "blocked": False,
                "reranked_count": len(ranked_docs),
                "expansion_strategies": len(queries_to_run)
            }
        )

        return QueryResponse(
            answer=answer, 
            sources=ranked_docs, 
            warning=warning,
            user=current_user.username
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

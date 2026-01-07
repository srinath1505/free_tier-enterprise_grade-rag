from sentence_transformers import CrossEncoder
from typing import List, Dict, Any, Tuple
import time
import logging

logger = logging.getLogger("rag_reranker")

class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-TinyBERT-L-2-v2"):
        """
        Initialize the Cross-Encoder model.
        TinyBERT is chosen for valid adherence to free-tier (CPU/RAM) constraints.
        """
        logger.info(f"Loading Reranker model: {model_name}")
        try:
            self.model = CrossEncoder(model_name, default_activation_function=None) # Logits or Sigmoid default
        except Exception as e:
            logger.error(f"Failed to load Reranker model: {e}")
            raise e

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Reranks a list of documents based on relevance to the query.
        Returns the top_k sorted documents.
        """
        if not documents:
            return []
            
        # Prepare pairs for Cross-Encoder
        # Check if 'content' vs 'text' key is used. We enforced 'content' in ingestion.
        passages = [doc.get('content', '') for doc in documents]
        
        # Guard against missing content
        valid_passages = []
        valid_indices = []
        for i, p in enumerate(passages):
            if p.strip():
                valid_passages.append(p)
                valid_indices.append(i)
        
        if not valid_passages:
            logger.warning("No valid content found in documents for reranking.")
            return documents[:top_k]

        pairs = [[query, passage] for passage in valid_passages]
        
        start = time.time()
        # Predict scores
        scores = self.model.predict(pairs)
        latency = (time.time() - start) * 1000
        logger.info(f"Reranked {len(pairs)} documents in {latency:.0f}ms")
        
        # Combine scores with original docs
        ranked_results = []
        for i, score in enumerate(scores):
            original_idx = valid_indices[i]
            doc = documents[original_idx].copy()
            doc['rerank_score'] = float(score)
            ranked_results.append(doc)
            
        # Sort by score descending
        ranked_results.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        return ranked_results[:top_k]

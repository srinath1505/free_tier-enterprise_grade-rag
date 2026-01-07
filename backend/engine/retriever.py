from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from backend.engine.vector_store import VectorStore
from backend.core.config import settings
import numpy as np

class HybridRetriever:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.bm25 = None
        self.documents = []  # In-memory docs for BM25. For production, efficient disk-based usage might be needed.
        
        # Initialize BM25 if there's data
        if self.vector_store.metadata:
            self._rebuild_bm25()

    def _rebuild_bm25(self):
        # Extract text content from metadata for BM25
        # Assuming metadata has 'content' or 'text' field
        self.documents = [m.get('content', '') for m in self.vector_store.metadata]
        tokenized_corpus = [doc.split(" ") for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, k: int = settings.TOP_K_RETRIEVAL, alpha: float = 0.5) -> List[Dict[str, Any]]:
        # 1. Vector Search
        vector_results = self.vector_store.search(query, k=k)
        
        # 2. Keyword Search (BM25)
        keyword_results = []
        if self.bm25:
            tokenized_query = query.split(" ")
            # Get scores
            doc_scores = self.bm25.get_scores(tokenized_query)
            # Get top k indices
            top_n = np.argsort(doc_scores)[::-1][:k]
            for idx in top_n:
                if idx < len(self.vector_store.metadata):
                    item = self.vector_store.metadata[idx].copy()
                    item['score'] = doc_scores[idx]
                    keyword_results.append(item)

        # 3. Weighted Reciprocal Rank Fusion
        return self._weighted_reciprocal_rank_fusion(vector_results, keyword_results, k=k, alpha=alpha)

    def _weighted_reciprocal_rank_fusion(self, 
                                list1: List[Dict[str, Any]], 
                                list2: List[Dict[str, Any]], 
                                k: int = 5, 
                                c: int = 60,
                                alpha: float = 0.5) -> List[Dict[str, Any]]:
        """
        Combines two lists of results using Weighted RRF.
        score = (alpha * (1 / (rank_vec + c))) + ((1 - alpha) * (1 / (rank_bm25 + c)))
        """
        rrf_score = {}
        
        # Helper to map content/id to object to deduplicate
        content_map = {}

        # Process Vector Results (list1) -> Tied to Alpha
        for rank, item in enumerate(list1):
            doc_id = item.get('id', hash(item.get('content', '')))
            content_map[doc_id] = item
            # Contribution from Vector Search
            rrf_score[doc_id] = rrf_score.get(doc_id, 0) + (alpha * (1 / (rank + 1 + c)))

        # Process Keyword Results (list2) -> Tied to (1 - Alpha)
        for rank, item in enumerate(list2):
            doc_id = item.get('id', hash(item.get('content', '')))
            if doc_id not in content_map:
                content_map[doc_id] = item
            # Contribution from Keyword Search
            rrf_score[doc_id] = rrf_score.get(doc_id, 0) + ((1 - alpha) * (1 / (rank + 1 + c)))

        # Sort by RRF score
        sorted_ids = sorted(rrf_score.keys(), key=lambda x: rrf_score[x], reverse=True)
        
        final_results = []
        for doc_id in sorted_ids[:k]:
            item = content_map[doc_id]
            item['rrf_score'] = rrf_score[doc_id]
            final_results.append(item)
            
        return final_results

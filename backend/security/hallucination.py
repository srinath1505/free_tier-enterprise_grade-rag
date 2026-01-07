from typing import List, Tuple
from sentence_transformers import SentenceTransformer, util
from backend.core.config import settings
import torch

class HallucinationDetector:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HallucinationDetector, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._model is None:
            # Load model only once (Singleton pattern for memory efficiency)
            # We use the same model as the retriever to keep memory footprint low
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        
        # Threshold: conservative 0.5. 
        # Sentences dealing with the same topic usually have > 0.5 similarity.
        # Below this likely means the answer drifted significantly.
        self.threshold = 0.5 

    def check_grounding(self, answer: str, context_chunks: List[str]) -> Tuple[bool, float, str]:
        """
        Checks if the answer is grounded in the context.
        Returns: (is_grounded, max_similarity_score, reason)
        """
        if not context_chunks:
             return False, 0.0, "No context provided."

        # Compute embeddings
        # convert_to_tensor=True for PyTorch implementation in util.cos_sim
        answer_emb = self._model.encode(answer, convert_to_tensor=True)
        context_embs = self._model.encode(context_chunks, convert_to_tensor=True)

        # Calculate cosine similarity between answer and ALL context chunks
        # We want to find if *at least one* chunk supports the answer.
        cosine_scores = util.cos_sim(answer_emb, context_embs)[0]
        max_score = float(torch.max(cosine_scores))

        is_grounded = max_score >= self.threshold
        reason = "Grounded in context." if is_grounded else f"Potential Hallucination (Score: {max_score:.2f} < {self.threshold})"
        
        return is_grounded, max_score, reason

from typing import List
import logging
from backend.engine.llm import get_llm

logger = logging.getLogger("rag_query_expander")

class QueryExpander:
    def __init__(self):
        self.llm = get_llm()

    def generate_variations(self, original_query: str, num_variations: int = 3) -> List[str]:
        """
        Generates alternative search queries using the LLM.
        """
        logger.info(f"Expanding query: {original_query}")
        
        system_prompt = (
            "You are a helpful expert research assistant. "
            "Your users are asking questions about specific documents. "
            f"Suggest up to {num_variations} alternative search queries that are related to the original question. "
            "These alternatives should cover different keywords or perspectives to maximize the chance of finding relevant documents in a vector database. "
            "Output ONLY the queries, one per line. Do not number them."
        )
        
        try:
            # We use the LLM to generate the variations
            # Note: This adds latency!
            response = self.llm.generate(original_query, system_prompt=system_prompt)
            
            # Parse response
            variations = [line.strip() for line in response.split('\n') if line.strip()]
            
            # Fallback if LLM creates numbering (e.g. "1. Query")
            cleaned_variations = []
            for v in variations:
                # Remove leading numbers/bullets
                v_clean = v.lstrip('0123456789.-* ')
                if v_clean:
                    cleaned_variations.append(v_clean)
            
            # Ensure we don't have too many
            final_variations = cleaned_variations[:num_variations]
            
            logger.info(f"Generated {len(final_variations)} variations: {final_variations}")
            return final_variations
            
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            # Fallback to just the original query if expansion fails
            return [original_query]

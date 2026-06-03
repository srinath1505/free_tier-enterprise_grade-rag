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
        
        from backend.engine.llm import LLMError
        try:
            response = self.llm.generate(original_query, system_prompt=system_prompt)

            variations = [line.strip() for line in response.split('\n') if line.strip()]
            cleaned_variations = []
            for v in variations:
                v_clean = v.lstrip('0123456789.-* ')
                if v_clean:
                    cleaned_variations.append(v_clean)

            final_variations = cleaned_variations[:num_variations]
            logger.info(f"Generated {len(final_variations)} variations: {final_variations}")
            return final_variations

        except LLMError:
            raise  # let caller decide — rag.py skips expansion when LLM is offline
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return []

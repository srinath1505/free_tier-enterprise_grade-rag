from typing import List
import logging
import numpy as np
from backend.engine.llm import get_llm

logger = logging.getLogger("rag_query_expander")

# Small models frequently "helpfully" reword a question even when told to leave standalone
# questions unchanged (e.g. "What algorithms does it use?" -> "What algorithms are utilized
# by the system?"). That churns the semantic cache key for no benefit, so any rewrite that's
# really just a paraphrase of the original gets discarded in favor of the original wording.
REWRITE_SIMILARITY_THRESHOLD = 0.9

# Separately, small models sometimes don't just paraphrase but balloon a short question into
# a long rambling one once there's conversation history to (over)react to — e.g. a 7-word
# question coming back as an 85-word run-on covering half the conversation. A rewrite that
# large is a failure mode, not a legitimate contextualization, so it's rejected outright
# rather than trusting it as the retrieval query.
MAX_REWRITE_EXTRA_WORDS = 20


class QueryExpander:
    def __init__(self, embeddings):
        self.llm = get_llm()
        self.embeddings = embeddings

    def contextualize(self, query: str, recent_turns: List[str]) -> str:
        """
        Rewrites a possibly follow-up query (e.g. "what about its performance?")
        into a standalone query using recent conversation turns, so retrieval
        doesn't have to resolve pronouns/ellipsis on its own.
        """
        if not recent_turns:
            return query

        history_text = "\n".join(recent_turns)
        system_prompt = (
            "You rewrite a user's latest question into a standalone question that makes sense "
            "without the conversation history, by resolving pronouns and implicit references. "
            "If the question is already standalone, return it unchanged. "
            "Output ONLY the rewritten question, nothing else."
        )
        prompt = f"Conversation so far:\n{history_text}\n\nLatest question: {query}"

        from backend.engine.llm import LLMError
        try:
            rewritten = self.llm.generate(prompt, system_prompt=system_prompt).strip()
        except LLMError:
            return query
        except Exception as e:
            logger.error(f"Query contextualization failed: {e}")
            return query

        if not rewritten:
            return query

        if len(rewritten.split()) > len(query.split()) + MAX_REWRITE_EXTRA_WORDS:
            logger.warning(f"Rewrite rejected as runaway ({len(rewritten.split())} words): {rewritten!r}")
            return query

        orig_emb = np.array(self.embeddings.embed_query(query))
        new_emb = np.array(self.embeddings.embed_query(rewritten))
        if float(orig_emb @ new_emb) > REWRITE_SIMILARITY_THRESHOLD:
            return query  # just a paraphrase — keep the original wording

        return rewritten

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

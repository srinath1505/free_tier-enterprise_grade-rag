import logging
from typing import List
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.memory import Memory
from backend.engine.llm import get_llm, LLMError

logger = logging.getLogger("rag_memory")

DEDUP_THRESHOLD = 0.9
# Small local models (e.g. phi3:mini) frequently ignore "facts about the USER only" and
# extract paraphrases of the answer instead. Those paraphrases are semantically close to the
# answer text; genuine user facts (preferences, role) are not — this threshold separates them
# regardless of which LLM backend produced the candidate, so it's a backend-agnostic safety net.
ANSWER_SIMILARITY_THRESHOLD = 0.6

EXTRACTION_SYSTEM_PROMPT = (
    "You extract facts ABOUT THE USER THEMSELVES — their role, what they work with, or "
    "preferences they stated about how to talk to them. You do NOT extract facts about the "
    "topic they asked about, and you do NOT summarize the assistant's answer — that is a "
    "different, common mistake to avoid. Use ONLY things the user explicitly said about "
    "themselves. Never invent, assume, or infer. Most exchanges are just Q&A about a topic and "
    "contain nothing about the user — in that case output exactly: NONE. "
    "Output one short fact per line, each under 15 words. If nothing qualifies, output: NONE\n\n"
    "Example 1 (user states something about themselves):\n"
    "User: I mostly work with PostgreSQL 16, keep answers short.\n"
    "Assistant: Got it.\n"
    "Output:\nWorks with PostgreSQL 16\nPrefers short answers\n\n"
    "Example 2 (plain factual Q&A, nothing about the user):\n"
    "User: What is the capital of France?\n"
    "Assistant: The capital of France is Paris.\n"
    "Output:\nNONE\n\n"
    "Example 3 (plain factual Q&A about the product — still nothing about the user):\n"
    "User: What does the reranker do?\n"
    "Assistant: It re-scores retrieved chunks to improve precision.\n"
    "Output:\nNONE"
)


class MemoryManager:
    """Long-term (plaintext) memory: durable per-user facts, separate from the
    per-document knowledge base. Reuses the embedding model already loaded by
    VectorStore instead of loading a second copy."""

    def __init__(self, embeddings):
        self.embeddings = embeddings

    async def get_relevant(self, db: AsyncSession, user_id: int, query: str, limit: int = 5) -> List[str]:
        result = await db.execute(select(Memory).where(Memory.user_id == user_id))
        rows = result.scalars().all()
        if not rows:
            return []

        contents = [r.content for r in rows]
        doc_embs = np.array(self.embeddings.embed_documents(contents))
        query_emb = np.array(self.embeddings.embed_query(query))
        # embeddings are normalized (normalize_embeddings=True), so dot product == cosine similarity
        scores = doc_embs @ query_emb
        top_idx = np.argsort(scores)[::-1][:limit]
        return [contents[i] for i in top_idx]

    def extract_facts(self, query: str, answer: str) -> List[str]:
        prompt = f"User: {query}\nAssistant: {answer}"
        try:
            response = get_llm().generate(prompt, system_prompt=EXTRACTION_SYSTEM_PROMPT)
        except LLMError as e:
            logger.warning(f"Memory extraction skipped — LLM unavailable: {e}")
            return []

        lines = [line.strip().lstrip("0123456789.-* ") for line in response.split("\n") if line.strip()]
        candidates = [
            line for line in lines
            if line and not line.upper().startswith("NONE")
            # small models occasionally hallucinate a fake extra exchange instead of a fact —
            # a literal "User:"/"Assistant:" prefix is a reliable tell for that failure mode
            and not line.lower().startswith(("user:", "assistant:"))
        ]
        if not candidates:
            return []

        # Backend-agnostic guard: drop any candidate that's really just a paraphrase of the
        # answer (see ANSWER_SIMILARITY_THRESHOLD) rather than a fact about the user.
        answer_emb = np.array(self.embeddings.embed_query(answer))
        candidate_embs = np.array(self.embeddings.embed_documents(candidates))
        sims = candidate_embs @ answer_emb
        return [c for c, s in zip(candidates, sims) if s < ANSWER_SIMILARITY_THRESHOLD]

    async def upsert_facts(self, db: AsyncSession, user_id: int, facts: List[str]) -> None:
        if not facts:
            return

        result = await db.execute(select(Memory).where(Memory.user_id == user_id))
        existing_contents = [r.content for r in result.scalars().all()]
        existing_embs = np.array(self.embeddings.embed_documents(existing_contents)) if existing_contents else None

        new_embs = np.array(self.embeddings.embed_documents(facts))
        added = 0
        for i, fact in enumerate(facts):
            if existing_embs is not None and len(existing_embs) > 0:
                if float(np.max(existing_embs @ new_embs[i])) > DEDUP_THRESHOLD:
                    continue
            db.add(Memory(user_id=user_id, content=fact))
            added += 1

        if added:
            await db.commit()

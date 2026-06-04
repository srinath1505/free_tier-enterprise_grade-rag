#!/usr/bin/env python3
"""
RAGAS Benchmarking for Enterprise RAG Pipeline
===============================================
Metrics:
  Faithfulness             - claims in the answer are supported by retrieved context
  Response Relevancy       - answer is semantically aligned with the question
  Context Precision        - retrieved chunks are relevant to the question
  Context Recall           - retrieved chunks cover the information in the ground truth

Usage:
  # From project root:
  python backend/scripts/ragas_benchmark.py
  python backend/scripts/ragas_benchmark.py --ingest        # re-ingest ragas_docs first
  python backend/scripts/ragas_benchmark.py --samples 10    # run subset of Q&A pairs
  python backend/scripts/ragas_benchmark.py --out results.json
"""

import os, sys, json, time, logging, argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

# ── project root on path ────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("ragas_bench")

# ── Q&A evaluation set ──────────────────────────────────────────────────────
# 25 pairs whose ground-truth answers are explicitly stated in the three
# sample documents in data/ragas_docs/.
QA_PAIRS: List[Dict[str, str]] = [
    # doc 01 – RAG architecture
    {
        "question": "What does RAG stand for?",
        "ground_truth": "RAG stands for Retrieval Augmented Generation.",
    },
    {
        "question": "What are the three main components of a RAG pipeline?",
        "ground_truth": (
            "The three main components are the retriever, the reranker, and "
            "the generator (LLM)."
        ),
    },
    {
        "question": "What is hybrid search in the context of RAG?",
        "ground_truth": (
            "Hybrid search combines dense vector similarity search with sparse "
            "keyword-based BM25 retrieval, blended by an alpha parameter between 0 and 1."
        ),
    },
    {
        "question": "What is the purpose of the reranker in a RAG pipeline?",
        "ground_truth": (
            "The reranker re-scores retrieved candidates using a cross-encoder model "
            "and selects the top-k most relevant chunks to pass as context to the LLM."
        ),
    },
    {
        "question": "What chunking strategy does the system use?",
        "ground_truth": (
            "The system uses semantic chunking based on sentence boundaries, with a "
            "target chunk size of 500 characters and a 50-character overlap."
        ),
    },
    {
        "question": "What is query expansion and why is it used?",
        "ground_truth": (
            "Query expansion generates alternative phrasings of the user question using "
            "the LLM so the retriever can find relevant documents that may not match the "
            "original wording."
        ),
    },
    {
        "question": "How is the confidence score calculated?",
        "ground_truth": (
            "Confidence is computed from the reranker top logit (60%), the grounding "
            "score (35%), and a source count bonus (5%). A 25% penalty is applied when "
            "the answer is not grounded."
        ),
    },
    {
        "question": "What does an alpha value of 0 mean in hybrid search?",
        "ground_truth": (
            "An alpha value of 0 means only keyword BM25 search is used, with no "
            "contribution from semantic vector search."
        ),
    },
    {
        "question": "What LLM providers does the system support?",
        "ground_truth": (
            "The system supports Ollama for local inference, Hugging Face Inference API, "
            "and Groq API with the Gemma2-9B-IT model."
        ),
    },
    # doc 02 – embeddings & retrieval
    {
        "question": "Which embedding model does the system use?",
        "ground_truth": (
            "The system uses all-MiniLM-L6-v2 from sentence-transformers, which produces "
            "384-dimensional dense embedding vectors."
        ),
    },
    {
        "question": "How many dimensions does the all-MiniLM-L6-v2 model produce?",
        "ground_truth": "The all-MiniLM-L6-v2 model produces 384-dimensional embeddings.",
    },
    {
        "question": "What FAISS index type does the system use?",
        "ground_truth": (
            "The system uses a FAISS IndexFlatIP index, which performs exact inner "
            "product similarity search."
        ),
    },
    {
        "question": "What cross-encoder model is used for reranking?",
        "ground_truth": (
            "The system uses cross-encoder/ms-marco-TinyBERT-L-2-v2, a lightweight "
            "model trained on MS MARCO passage ranking data."
        ),
    },
    {
        "question": "How does a cross-encoder differ from a bi-encoder?",
        "ground_truth": (
            "A cross-encoder jointly encodes a query-document pair together for a single "
            "relevance score, while a bi-encoder encodes query and document separately. "
            "Cross-encoders are more accurate but slower."
        ),
    },
    {
        "question": "What similarity metric does FAISS use for retrieval?",
        "ground_truth": (
            "FAISS uses inner product similarity, which is equivalent to cosine similarity "
            "because embeddings are L2-normalized before storage."
        ),
    },
    {
        "question": "What is the hallucination detection threshold?",
        "ground_truth": (
            "If the maximum cosine similarity between the answer embedding and any context "
            "chunk embedding is below 0.5, the answer is flagged as potentially not grounded."
        ),
    },
    {
        "question": "Which file formats does the ingestion pipeline support?",
        "ground_truth": "The pipeline supports PDF, DOCX, and TXT file formats.",
    },
    # doc 03 – security & administration
    {
        "question": "What authentication mechanism does the system use?",
        "ground_truth": (
            "The system uses JSON Web Tokens (JWT) signed with the HS256 algorithm."
        ),
    },
    {
        "question": "What are the two user roles in the system?",
        "ground_truth": (
            "The two roles are admin, who can manage documents and view analytics, "
            "and viewer, who can only query the knowledge base."
        ),
    },
    {
        "question": "How are passwords hashed in the system?",
        "ground_truth": (
            "Passwords are hashed using PBKDF2-SHA256 via the passlib library."
        ),
    },
    {
        "question": "What is the maximum allowed file upload size?",
        "ground_truth": "The maximum allowed upload size is 50 MB per file.",
    },
    {
        "question": "What happens to vectors when a document is deleted?",
        "ground_truth": (
            "Vectors remain in the FAISS index after file deletion until the index "
            "is explicitly rebuilt, which re-ingests all remaining files from scratch."
        ),
    },
    {
        "question": "What rate limiting library does the system use?",
        "ground_truth": (
            "The system uses slowapi for per-IP request throttling."
        ),
    },
    {
        "question": "What data does the analytics dashboard display?",
        "ground_truth": (
            "The analytics dashboard shows queries today, total queries, average response "
            "time, failed queries, top questions by frequency, and a recent query log."
        ),
    },
    {
        "question": "What two files make up the vector store on disk?",
        "ground_truth": (
            "The vector store consists of index.faiss containing embedding vectors and "
            "metadata.json containing chunk text and document metadata."
        ),
    },
]


# ── ingest sample docs ──────────────────────────────────────────────────────
def ingest_ragas_docs() -> None:
    """Ingest the three sample docs in data/ragas_docs/ into the vector store."""
    from ingestion.loaders.txt import TXTLoader
    from ingestion.chunker import SemanticChunker
    from backend.engine.vector_store import VectorStore

    docs_dir = ROOT / "data" / "ragas_docs"
    if not docs_dir.exists():
        raise FileNotFoundError(f"Sample docs not found at {docs_dir}")

    vs = VectorStore()
    chunker = SemanticChunker()
    total_chunks = 0

    for txt_path in sorted(docs_dir.glob("*.txt")):
        print(f"  Ingesting {txt_path.name} …", end=" ", flush=True)
        loader = TXTLoader(str(txt_path))
        raw_docs = loader.load()
        chunks = chunker.chunk(raw_docs)
        if chunks:
            texts = [c["content"] for c in chunks]
            metas = [{**c["metadata"], "content": c["content"]} for c in chunks]
            vs.add_documents(texts, metas)
            total_chunks += len(chunks)
        print(f"{len(chunks)} chunks")

    print(f"  Total chunks ingested: {total_chunks}")

    # rebuild BM25 index
    try:
        from backend.engine.retriever import HybridRetriever
        HybridRetriever(vs)._rebuild_bm25()
    except Exception:
        pass


# ── run one RAG query ────────────────────────────────────────────────────────
def run_rag_query(
    question: str,
    retriever,
    reranker,
    llm,
    top_k: int = 5,
    alpha: float = 0.5,
) -> Dict[str, Any]:
    """Run the full retrieval + reranking + generation pipeline for one question."""
    # 1. Retrieve
    docs = retriever.search(question, k=top_k, alpha=alpha)

    # 2. Rerank → top 3
    ranked = reranker.rerank(question, docs, top_k=3) if docs else []

    # 3. Build context
    contexts = [d.get("content", "") for d in ranked]
    context_text = "\n\n".join(
        f"[Source {i+1}]: {c}" for i, c in enumerate(contexts)
    ) or "No relevant documents found."

    # 4. Generate
    system_prompt = (
        "You are a helpful assistant. Answer the question using only the provided context. "
        "Be concise and factual.\n\nContext:\n" + context_text
    )
    try:
        answer = llm.generate(question, system_prompt=system_prompt)
    except Exception as e:
        answer = f"[LLM Error: {e}]"

    return {"answer": answer, "contexts": contexts, "ranked_docs": ranked}


# ── configure RAGAS LLM ──────────────────────────────────────────────────────
def build_ragas_llm_and_embeddings(groq_key: Optional[str], groq_model: str):
    """Return (ragas_llm, ragas_embeddings) using available provider."""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from backend.core.config import settings

    emb_model = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # Try ragas 0.2.x wrappers first, fall back to 0.1.x global config
    try:
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        ragas_emb = LangchainEmbeddingsWrapper(emb_model)

        if groq_key:
            from langchain_groq import ChatGroq
            lc_llm = ChatGroq(model=groq_model, groq_api_key=groq_key, temperature=0)
            ragas_llm = LangchainLLMWrapper(lc_llm)
            print(f"  RAGAS evaluator: Groq / {groq_model}")
        else:
            from langchain_community.chat_models import ChatOllama
            from backend.core.config import settings as s
            lc_llm = ChatOllama(model=s.OLLAMA_MODEL, base_url=s.OLLAMA_BASE_URL)
            ragas_llm = LangchainLLMWrapper(lc_llm)
            print(f"  RAGAS evaluator: Ollama / {s.OLLAMA_MODEL}")

        return ragas_llm, ragas_emb

    except ImportError:
        # ragas 0.1.x — LLM is set globally / per-metric
        return None, None


# ── evaluate with RAGAS ──────────────────────────────────────────────────────
def evaluate_ragas(
    questions: List[str],
    answers: List[str],
    contexts: List[List[str]],
    ground_truths: List[str],
    ragas_llm,
    ragas_emb,
) -> Dict[str, Any]:
    """Run RAGAS evaluate(), handling both 0.2.x and 0.1.x APIs."""

    # ── Try ragas 0.2.x ──────────────────────────────────────────────────
    try:
        from ragas import evaluate, EvaluationDataset, SingleTurnSample
        from ragas.metrics import (
            Faithfulness,
            ResponseRelevancy,
            LLMContextPrecisionWithoutReference,
            LLMContextRecall,
        )

        samples = [
            SingleTurnSample(
                user_input=q,
                response=a,
                retrieved_contexts=c,
                reference=gt,
            )
            for q, a, c, gt in zip(questions, answers, contexts, ground_truths)
        ]
        dataset = EvaluationDataset(samples=samples)

        metrics = [
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithoutReference(),
            LLMContextRecall(),
        ]

        kwargs: Dict[str, Any] = {"dataset": dataset, "metrics": metrics}
        if ragas_llm:
            kwargs["llm"] = ragas_llm
        if ragas_emb:
            kwargs["embeddings"] = ragas_emb

        result = evaluate(**kwargs)
        return dict(result)

    except (ImportError, AttributeError):
        pass

    # ── Fall back to ragas 0.1.x ─────────────────────────────────────────
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from datasets import Dataset

    if ragas_llm:
        for metric in [faithfulness, answer_relevancy, context_precision, context_recall]:
            if hasattr(metric, "llm"):
                metric.llm = ragas_llm
            if hasattr(metric, "embeddings") and ragas_emb:
                metric.embeddings = ragas_emb

    ds = Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }
    )

    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    return dict(result)


# ── pretty-print results ─────────────────────────────────────────────────────
def print_report(results: Dict[str, Any], per_sample: List[Dict], elapsed: float) -> None:
    LINE = "─" * 62
    print(f"\n{'═'*62}")
    print("  RAGAS BENCHMARK RESULTS — Enterprise RAG Pipeline")
    print(f"{'═'*62}")

    metric_map = {
        "faithfulness":                          "Faithfulness",
        "answer_relevancy":                      "Answer Relevancy",
        "response_relevancy":                    "Response Relevancy",
        "context_precision":                     "Context Precision",
        "llm_context_precision_without_reference": "Context Precision",
        "context_recall":                        "Context Recall",
        "llm_context_recall":                    "Context Recall",
    }

    print(f"\n  {'Metric':<32} {'Score':>8}  {'Rating'}")
    print(f"  {LINE}")
    for raw_key, score in results.items():
        label = metric_map.get(raw_key, raw_key)
        if not isinstance(score, float):
            continue
        if   score >= 0.85: rating = "Excellent"
        elif score >= 0.70: rating = "Good"
        elif score >= 0.55: rating = "Fair"
        elif score >= 0.40: rating = "Poor"
        else:               rating = "Very Poor"
        bar = "█" * int(score * 20)
        print(f"  {label:<32} {score:>7.3f}  {rating}  {bar}")

    print(f"\n  Samples evaluated : {len(per_sample)}")
    print(f"  Pipeline runtime  : {elapsed:.1f}s  "
          f"({elapsed/len(per_sample):.1f}s / query)")

    print(f"\n  {'#':<4} {'Question (truncated)':<40} Ans? Ctx?")
    print(f"  {LINE}")
    for i, s in enumerate(per_sample, 1):
        q = s["question"][:38] + ("…" if len(s["question"]) > 38 else "")
        has_ans = "✓" if s["answer"] and not s["answer"].startswith("[LLM") else "✗"
        has_ctx = "✓" if s["contexts"] else "✗"
        print(f"  {i:<4} {q:<40} {has_ans:<5}{has_ctx}")
    print(f"{'═'*62}\n")


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="RAGAS benchmark for Enterprise RAG")
    parser.add_argument("--ingest", action="store_true",
                        help="Ingest sample docs before benchmarking")
    parser.add_argument("--samples", type=int, default=len(QA_PAIRS),
                        help=f"Number of Q&A pairs to evaluate (max {len(QA_PAIRS)})")
    parser.add_argument("--alpha", type=float, default=0.5,
                        help="Hybrid search alpha (0=BM25, 1=semantic)")
    parser.add_argument("--out", type=str, default="ragas_results.json",
                        help="Path to write JSON results")
    args = parser.parse_args()

    print("\nEnterprise RAG – RAGAS Benchmark")
    print("=" * 40)

    # ── optional ingestion ──────────────────────────────────────────────
    if args.ingest:
        print("\n[1/4] Ingesting sample documents …")
        ingest_ragas_docs()
    else:
        print("\n[1/4] Skipping ingestion (use --ingest to re-ingest)")

    # ── load pipeline components ────────────────────────────────────────
    print("\n[2/4] Loading pipeline components …")
    from backend.engine.vector_store import VectorStore
    from backend.engine.retriever import HybridRetriever
    from backend.engine.reranker import Reranker
    from backend.engine.llm import get_llm
    from backend.core.config import settings

    vs       = VectorStore()
    retriever = HybridRetriever(vs)
    reranker  = Reranker()
    llm       = get_llm()
    print(f"  Vector store: {vs.index.ntotal if vs.index else 0} vectors")
    print(f"  LLM provider: {settings.LLM_PROVIDER}")

    # ── build RAGAS evaluator ───────────────────────────────────────────
    print("\n[3/4] Configuring RAGAS evaluator …")
    groq_key   = os.getenv("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
    groq_model = getattr(settings, "GROQ_MODEL", "gemma2-9b-it")
    ragas_llm, ragas_emb = build_ragas_llm_and_embeddings(groq_key, groq_model)

    # ── run RAG pipeline on each question ───────────────────────────────
    print(f"\n[4/4] Running {args.samples} queries through RAG pipeline …")
    pairs = QA_PAIRS[: args.samples]
    questions, answers, contexts, ground_truths = [], [], [], []
    per_sample: List[Dict] = []
    t0 = time.time()

    for i, pair in enumerate(pairs, 1):
        q  = pair["question"]
        gt = pair["ground_truth"]
        print(f"  [{i:>2}/{args.samples}] {q[:60]}", end=" … ", flush=True)
        out = run_rag_query(q, retriever, reranker, llm, alpha=args.alpha)
        questions.append(q)
        answers.append(out["answer"])
        contexts.append(out["contexts"])
        ground_truths.append(gt)
        per_sample.append({"question": q, "answer": out["answer"],
                            "contexts": out["contexts"]})
        print("done" if not out["answer"].startswith("[LLM") else "LLM error")

    elapsed = time.time() - t0

    # ── RAGAS evaluation ────────────────────────────────────────────────
    print("\nRunning RAGAS evaluation (this may take a few minutes) …")
    try:
        ragas_scores = evaluate_ragas(
            questions, answers, contexts, ground_truths, ragas_llm, ragas_emb
        )
    except Exception as e:
        print(f"\nRAGAS evaluation error: {e}")
        ragas_scores = {}

    # ── report ──────────────────────────────────────────────────────────
    print_report(ragas_scores, per_sample, elapsed)

    # ── save JSON ───────────────────────────────────────────────────────
    out_path = Path(args.out) if Path(args.out).is_absolute() else ROOT / args.out
    payload = {
        "ragas_scores": ragas_scores,
        "samples_evaluated": len(pairs),
        "pipeline_runtime_s": round(elapsed, 2),
        "alpha": args.alpha,
        "per_sample": [
            {
                "question":     s["question"],
                "answer":       s["answer"][:300],
                "context_count": len(s["contexts"]),
                "ground_truth": pairs[i]["ground_truth"],
            }
            for i, s in enumerate(per_sample)
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Results saved → {out_path}\n")


if __name__ == "__main__":
    main()
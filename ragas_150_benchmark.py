#!/usr/bin/env python3
"""
RAGAS evaluation over the full 150-question benchmark dataset.

Metrics (no ground truth required):
  - Faithfulness                       answers are grounded in retrieved context
  - Response Relevancy                 answers are semantically aligned with the question
  - LLM Context Precision (no ref)     retrieved chunks are relevant to the question

Answers are loaded from benchmark_results_final.json (already generated).
Contexts are obtained by re-running retrieval against benchmark_vector_store/.

Usage:
  python ragas_150_benchmark.py
  python ragas_150_benchmark.py --out ragas_150_scores.json
  python ragas_150_benchmark.py --source langchain        # subset by source
  python ragas_150_benchmark.py --difficulty adversarial  # subset by difficulty
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).parent

# Point to benchmark vector store BEFORE any backend import
BENCHMARK_VS = str(ROOT / "benchmark_vector_store")
os.environ["VECTOR_STORE_PATH"] = BENCHMARK_VS
os.environ.setdefault("LLM_PROVIDER", "groq")

sys.path.insert(0, str(ROOT))

from backend.core.config import settings           # noqa: E402
from backend.engine.reranker import Reranker       # noqa: E402
from backend.engine.retriever import HybridRetriever  # noqa: E402
from backend.engine.vector_store import VectorStore   # noqa: E402


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve_contexts(questions: list[str],
                      retriever: HybridRetriever,
                      reranker: Reranker) -> list[list[str]]:
    """Return top-3 reranked chunk texts for each question."""
    all_contexts: list[list[str]] = []
    for i, q in enumerate(questions, 1):
        print(f"  retrieving [{i:3d}/{len(questions)}] {q[:70]}", flush=True)
        docs = retriever.search(q, k=5)
        docs = reranker.rerank(q, docs, top_k=3)
        all_contexts.append([d.get("content", "") for d in docs if d.get("content")])
    return all_contexts


# ---------------------------------------------------------------------------
# RAGAS setup & evaluation
# ---------------------------------------------------------------------------

def build_ragas_llm_and_embeddings(api_key: str, model: str):
    from openai import OpenAI
    from ragas.llms import llm_factory
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_community.embeddings import HuggingFaceEmbeddings

    groq_client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    ragas_llm = llm_factory(model, client=groq_client)

    lc_emb = HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    ragas_emb = LangchainEmbeddingsWrapper(lc_emb)

    print(f"  RAGAS evaluator : Groq / {model}")
    print(f"  Embedding model : {settings.EMBEDDING_MODEL_NAME}")
    return ragas_llm, ragas_emb


def run_ragas(questions: list[str],
              answers: list[str],
              contexts: list[list[str]],
              ragas_llm,
              ragas_emb) -> dict:

    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from ragas import evaluate, EvaluationDataset, SingleTurnSample
    from ragas.metrics import faithfulness, answer_relevancy

    samples = [
        SingleTurnSample(
            user_input=q,
            response=a,
            retrieved_contexts=c,
        )
        for q, a, c in zip(questions, answers, contexts)
    ]

    dataset = EvaluationDataset(samples=samples)
    result  = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=ragas_llm,
        embeddings=ragas_emb,
    )
    # dict(result) is broken in RAGAS 0.4.3 — use to_pandas() instead
    df = result.to_pandas()
    metric_cols = [c for c in ["faithfulness", "answer_relevancy"] if c in df.columns]
    return {col: float(df[col].mean()) for col in metric_cols}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(scores: dict, n: int, elapsed: float,
                 by_source: dict, by_difficulty: dict) -> None:
    SEP = "=" * 62
    print(f"\n{SEP}")
    print("  RAGAS RESULTS -- 150-Question Benchmark")
    print(SEP)

    label_map = {
        "faithfulness":    "Faithfulness",
        "answer_relevancy": "Answer Relevancy",
    }

    print(f"\n  {'Metric':<36} {'Score':>7}  Rating")
    print("  " + "-" * 55)
    for key, label in label_map.items():
        val = scores.get(key)
        if val is None:
            continue
        if   val >= 0.85: rating = "Excellent"
        elif val >= 0.70: rating = "Good"
        elif val >= 0.55: rating = "Fair"
        else:             rating = "Poor"
        bar = "#" * int(val * 20)
        print(f"  {label:<36} {val:>7.3f}  {rating}  {bar}")

    print(f"\n  Samples evaluated : {n}")
    print(f"  Total runtime     : {elapsed/60:.1f} min")

    for split_name, split_data in (("Source", by_source),
                                   ("Difficulty", by_difficulty)):
        print(f"\n  -- by {split_name} " + "-" * 44)
        for group, group_scores in sorted(split_data.items()):
            parts = []
            for key, label in label_map.items():
                v = group_scores.get(key)
                if v is not None:
                    parts.append(f"{label.split()[0]}={v:.2f}")
            print(f"  {group:<14} {' | '.join(parts)}")

    print(SEP + "\n")


# ---------------------------------------------------------------------------
# Subset RAGAS helper
# ---------------------------------------------------------------------------

def score_subset(questions, answers, contexts, indices,
                 ragas_llm, ragas_emb) -> dict:
    sub_q = [questions[i] for i in indices]
    sub_a = [answers[i]   for i in indices]
    sub_c = [contexts[i]  for i in indices]
    if not sub_q:
        return {}
    try:
        return run_ragas(sub_q, sub_a, sub_c, ragas_llm, ragas_emb)
    except Exception as e:
        print(f"    subset RAGAS error: {e}")
        return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-file",  default="benchmark_results_final.json",
                        help="Path to benchmark_results_final.json")
    parser.add_argument("--questions-file", default="rag_benchmark_questions.json")
    parser.add_argument("--out",  default="ragas_150_scores.json")
    parser.add_argument("--source",     default="",
                        help="Filter by source: langchain | postgresql")
    parser.add_argument("--difficulty", default="",
                        help="Filter by difficulty: factual | reasoning | adversarial")
    args = parser.parse_args()

    # -- API key --------------------------------------------------------------
    api_key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY
    if not api_key:
        sys.exit("ERROR: GROQ_API_KEY not set. Add it to .env or export the env var.")
    eval_model = "llama-3.1-8b-instant"   # high-throughput model for evaluation

    # -- Load existing answers from benchmark_results_final.json -------------
    print(f"\n[1/4] Loading answers from {args.results_file} ...")
    with open(args.results_file, encoding="utf-8") as f:
        bench_data = json.load(f)

    rows = bench_data["individual_results"]

    # Apply optional filters
    if args.source:
        rows = [r for r in rows if r["source"] == args.source]
    if args.difficulty:
        rows = [r for r in rows if r["difficulty"] == args.difficulty]

    if not rows:
        sys.exit("ERROR: no rows match the filter criteria.")

    questions  = [r["question"] for r in rows]
    answers    = [r["answer"]   for r in rows]
    sources    = [r["source"]      for r in rows]
    difficulties = [r["difficulty"] for r in rows]

    print(f"  {len(rows)} questions loaded  "
          f"(sources: {set(sources)}  difficulties: {set(difficulties)})")

    # -- Build retrieval pipeline --------------------------------------------
    print("\n[2/4] Loading benchmark vector store and pipeline ...")
    vs        = VectorStore()
    retriever = HybridRetriever(vs)
    reranker  = Reranker()
    print(f"  Vector store : {vs.index.ntotal if vs.index else 0:,} vectors")
    print(f"  BM25 corpus  : {len(retriever.documents):,} docs")

    # -- Re-run retrieval to get contexts ------------------------------------
    print(f"\n[3/4] Retrieving contexts for {len(rows)} questions ...")
    t_ret = time.time()
    contexts = retrieve_contexts(questions, retriever, reranker)
    print(f"  Retrieval done in {(time.time()-t_ret):.1f}s")

    # -- Build RAGAS evaluator -----------------------------------------------
    print("\n[4/4] Running RAGAS evaluation ...")
    ragas_llm, ragas_emb = build_ragas_llm_and_embeddings(api_key, eval_model)

    t0 = time.time()
    print("  Evaluating full dataset ...")
    try:
        overall_scores = run_ragas(questions, answers, contexts, ragas_llm, ragas_emb)
    except Exception as e:
        sys.exit(f"RAGAS evaluation failed: {e}")

    # Per-source breakdown
    by_source: dict[str, dict] = {}
    for src in sorted(set(sources)):
        idx = [i for i, s in enumerate(sources) if s == src]
        print(f"  Evaluating subset: source={src} ({len(idx)} questions) ...")
        by_source[src] = score_subset(questions, answers, contexts, idx,
                                      ragas_llm, ragas_emb)

    # Per-difficulty breakdown
    by_difficulty: dict[str, dict] = {}
    for diff in sorted(set(difficulties)):
        idx = [i for i, d in enumerate(difficulties) if d == diff]
        print(f"  Evaluating subset: difficulty={diff} ({len(idx)} questions) ...")
        by_difficulty[diff] = score_subset(questions, answers, contexts, idx,
                                           ragas_llm, ragas_emb)

    elapsed = time.time() - t0

    # -- Report & save -------------------------------------------------------
    print_report(overall_scores, len(rows), elapsed, by_source, by_difficulty)

    payload = {
        "metadata": {
            "evaluated_at":    __import__("datetime").datetime.now().isoformat(),
            "results_source":  args.results_file,
            "total_questions": len(rows),
            "eval_model":      eval_model,
            "embedding_model": settings.EMBEDDING_MODEL_NAME,
            "vector_store":    BENCHMARK_VS,
            "filters":         {"source": args.source, "difficulty": args.difficulty},
            "note": (
                "Faithfulness and Answer Relevancy require no ground truth. "
                "Context Precision and Context Recall are omitted — both require "
                "reference answers which are not available for this dataset."
            ),
        },
        "overall": overall_scores,
        "by_source": by_source,
        "by_difficulty": by_difficulty,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Results saved -> {args.out}\n")


if __name__ == "__main__":
    main()
